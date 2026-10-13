"""Refresh flag catalogs for changed CLI registrations.

Entry point: python -m extractor.refresh --base <revision> --head <revision> [--no-push]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from extractor.cli_config import ObtainConfig, load_cli_config
from extractor.obtain import ObtainError, ObtainInstruction, obtain

# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------


def _changed_registration_paths(base: str, head: str, clis_dir: Path) -> dict[str, str]:
    """Return {tool_name: status} for registrations that differ between base and head.

    status is 'A' (added), 'M' (modified), or 'D' (deleted).
    head may be 'WORKTREE' to compare against the working tree.
    """
    if head == "WORKTREE":
        result = subprocess.run(
            ["git", "diff", "--name-status", base, "--", str(clis_dir) + "/*.yaml"],
            capture_output=True,
            text=True,
        )
    else:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--name-status",
                base,
                head,
                "--",
                str(clis_dir) + "/*.yaml",
            ],
            capture_output=True,
            text=True,
        )

    changed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        status_code, path = parts[0].strip(), parts[1].strip()
        # status_code may be R100 etc for renames — treat as modified
        status = status_code[0]
        if status not in ("A", "M", "D"):
            continue
        tool_name = Path(path).stem
        changed[tool_name] = status
    return changed


def _read_versions_at_revision(
    tool_name: str, revision: str, clis_dir: Path
) -> list[str]:
    """Return the declared versions for tool_name at git revision, or [] if not found."""
    path = clis_dir / f"{tool_name}.yaml"
    if revision == "WORKTREE":
        if not path.exists():
            return []
        import yaml

        data = yaml.safe_load(path.read_text())
        return data.get("versions", [])

    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    import yaml

    data = yaml.safe_load(result.stdout)
    return data.get("versions", [])


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def _extract_schema(binary_path: Path, config, version: str) -> dict:
    """Run the extractor adapter on the installed binary and return the schema dict."""
    import os
    import sys

    from extractor.adapters import cobra, help_parser
    from extractor.main import extract_custom

    adapter = config.adapter
    binary = str(binary_path)

    # Large CLIs (helm, kubectl) have deep subcommand trees that can exceed the default
    # recursion limit of 1000 in the cobra adapter's recursive traversal.
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(5000)

    env_path = str(binary_path.parent) + ":" + os.environ.get("PATH", "")
    old_path = os.environ.get("PATH")
    os.environ["PATH"] = env_path
    try:
        if adapter == "cobra":
            schema = cobra.extract(binary, version)
        elif adapter == "help-parser":
            schema = help_parser.extract(config, version)
        elif adapter == "custom":
            schema = extract_custom(config.extraction_script, config.name, version)
        else:
            raise RuntimeError(f"unsupported adapter {adapter!r}")
    finally:
        sys.setrecursionlimit(old_limit)
        if old_path is None:
            del os.environ["PATH"]
        else:
            os.environ["PATH"] = old_path

    if not schema.get("subcommands") and not schema.get("flags"):
        raise RuntimeError("catalog has no commands")
    return schema


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh CLI flag catalogs for changed registrations"
    )
    parser.add_argument(
        "--base", required=True, help="Base git revision (e.g. HEAD, SHA)"
    )
    parser.add_argument(
        "--head",
        default="WORKTREE",
        help="Head revision or WORKTREE (default: WORKTREE)",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Report differences instead of publishing (fork PR mode)",
    )
    parser.add_argument(
        "--clis-dir", default="clis", help="Directory containing CLI YAML registrations"
    )
    parser.add_argument(
        "--schemas-dir",
        default="schemas",
        help="Directory containing flag catalog JSON files",
    )
    args = parser.parse_args()

    clis_dir = Path(args.clis_dir)
    schemas_dir = Path(args.schemas_dir)

    changed = _changed_registration_paths(args.base, args.head, clis_dir)
    if not changed:
        print("catalogs already match")
        sys.exit(0)

    # Separate deletions from adds/modifies
    deleted_tools = {t for t, s in changed.items() if s == "D"}
    refreshed_tools = {t: s for t, s in changed.items() if s != "D"}

    # For each modified/added tool, determine versions to refresh and versions to retire
    # versions_to_refresh: {tool: [version, ...]}
    # versions_to_retire: {tool: [version, ...]} (versions in base but not in head)
    versions_to_refresh: dict[str, list[str]] = {}
    versions_to_retire: dict[str, list[str]] = {}

    for tool, status in refreshed_tools.items():
        head_versions = _read_versions_at_revision(tool, args.head, clis_dir)
        if status == "M":
            base_versions = _read_versions_at_revision(tool, args.base, clis_dir)
            retired = [v for v in base_versions if v not in head_versions]
            if retired:
                versions_to_retire[tool] = retired
        versions_to_refresh[tool] = head_versions

    # Extract into a temp dir (all-or-nothing)
    failures: list[str] = []
    # temp_results[tool][version] = path to extracted JSON
    temp_results: dict[str, dict[str, Path]] = {}

    with tempfile.TemporaryDirectory(prefix="extractor-refresh-") as tmpdir:
        tmp_path = Path(tmpdir)

        for tool, versions in versions_to_refresh.items():
            config_path = clis_dir / f"{tool}.yaml"
            try:
                config = load_cli_config(config_path)
            except Exception as exc:
                failures.append(f"FAIL {tool} <config> {exc}")
                continue

            if config.obtain is None:
                failures.append(f"FAIL {tool} <config> missing obtain block")
                continue

            ob: ObtainConfig = config.obtain
            instr = ObtainInstruction(
                artifact_url=ob.artifact_url,
                checksum_url=ob.checksum_url,
                format=ob.format,
                binary=ob.binary,
                version_url=ob.version_url,
                version_match=ob.version_match,
            )

            tool_results: dict[str, Path] = {}
            tool_ok = True

            for version in versions:
                version_tmp = tmp_path / tool / version
                version_tmp.mkdir(parents=True, exist_ok=True)
                bin_dir = version_tmp / "bin"
                bin_dir.mkdir(exist_ok=True)

                try:
                    binary_path = obtain(instr, version, bin_dir)
                except ObtainError as exc:
                    failures.append(f"FAIL {tool} {version} {exc}")
                    tool_ok = False
                    continue

                try:
                    schema = _extract_schema(binary_path, config, version)
                except Exception as exc:
                    failures.append(f"FAIL {tool} {version} {exc}")
                    tool_ok = False
                    continue

                schema["version"] = version
                out_json = version_tmp / f"{version}.json"
                out_json.write_text(json.dumps(schema, indent=2))
                tool_results[version] = out_json

            if tool_ok:
                temp_results[tool] = tool_results

        if failures:
            for line in failures:
                print(line)
            sys.exit(1)

        # Compute differences between temp results and current schemas/
        differing: list[str] = []
        published_paths: list[tuple[Path, Path]] = []
        retired_version_paths: list[Path] = []
        deleted_tool_dirs: list[Path] = []

        for tool, version_files in temp_results.items():
            for version, tmp_json in version_files.items():
                dest = schemas_dir / tool / f"{version}.json"
                if not dest.exists() or dest.read_bytes() != tmp_json.read_bytes():
                    differing.append(str(dest))
                    published_paths.append((tmp_json, dest))

        for tool, versions in versions_to_retire.items():
            for version in versions:
                path = schemas_dir / tool / f"{version}.json"
                if path.exists():
                    differing.append(str(path))
                    retired_version_paths.append(path)

        for tool in deleted_tools:
            tool_dir = schemas_dir / tool
            if tool_dir.exists():
                for f in sorted(tool_dir.iterdir()):
                    differing.append(str(f))
                deleted_tool_dirs.append(tool_dir)

        if not differing:
            print("catalogs already match")
            sys.exit(0)

        if args.no_push:
            print("catalogs differ:")
            for p in sorted(differing):
                print(p)
            print("not updated")
            sys.exit(2)

        # Publish: copy new files, delete retired ones
        for tmp_json, dest in published_paths:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tmp_json, dest)
            print(str(dest))

        for path in retired_version_paths:
            if path.exists():
                print(str(path))
                path.unlink()
                # Remove parent dir if now empty
                if not any(path.parent.iterdir()):
                    path.parent.rmdir()

        for tool_dir in deleted_tool_dirs:
            if tool_dir.exists():
                for f in sorted(tool_dir.iterdir()):
                    print(str(f))
                shutil.rmtree(tool_dir)

    print("published")
    sys.exit(0)


if __name__ == "__main__":
    main()
