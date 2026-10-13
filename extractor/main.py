"""Extractor entry point: python -m extractor <cli_name> <version> [--clis-dir clis] [--output schemas]."""

import json
import os
import subprocess
import sys
from pathlib import Path


def extract_custom(script: str, tool: str, version: str, config_path: Path | None = None) -> dict:
    """Run a custom extraction script and return the schema JSON object.

    The script is invoked as ``<script> <tool> <version>``. Python scripts that are not
    executable are run with the current interpreter. Non-zero exits and non-object JSON
    are errors.
    """
    if not script or not str(script).strip():
        raise ValueError("custom adapter requires extraction_script")

    script_path = Path(script)
    if not script_path.is_absolute() and config_path is not None:
        candidate = config_path.parent / script_path
        if candidate.exists():
            script_path = candidate
    if not script_path.exists():
        raise FileNotFoundError(f"extraction script not found: {script_path}")

    if script_path.suffix == ".py" or not os.access(script_path, os.X_OK):
        command = [sys.executable, str(script_path), tool, version]
    else:
        command = [str(script_path), tool, version]

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"extraction script exited {result.returncode}"
            + (f": {detail}" if detail else "")
        )
    try:
        schema = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"extraction script did not return JSON: {exc}") from exc
    if not isinstance(schema, dict):
        raise ValueError("extraction script JSON must be an object")
    return schema


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Extract CLI schema to JSON")
    parser.add_argument("cli", help="CLI name (must match a file in clis/)")
    parser.add_argument("version", help="Version to extract (must match a version in the YAML config)")
    parser.add_argument("--clis-dir", default="clis", help="Directory containing CLI YAML configs")
    parser.add_argument("--output", default="schemas", help="Output directory for schema JSON files")
    args = parser.parse_args()

    from extractor.adapters import cobra, help_parser
    from extractor.cli_config import load_cli_config

    clis_dir = Path(args.clis_dir)
    config_path = clis_dir / f"{args.cli}.yaml"
    if not config_path.exists():
        print(f"Error: no config found at {config_path}", file=sys.stderr)
        sys.exit(1)

    config = load_cli_config(config_path)

    if args.version not in config.versions:
        print(
            f"Error: version '{args.version}' not in {config_path} versions: {config.versions}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Extracting {config.name} {args.version} using adapter '{config.adapter}'...")

    try:
        if config.adapter == "cobra":
            schema = cobra.extract(config.binary, args.version)
        elif config.adapter == "help-parser":
            schema = help_parser.extract(config, args.version)
        elif config.adapter == "custom":
            schema = extract_custom(
                config.extraction_script, args.cli, args.version, config_path
            )
        else:
            print(f"Error: unsupported adapter '{config.adapter}'", file=sys.stderr)
            sys.exit(1)
    except (OSError, subprocess.TimeoutExpired, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output) / config.name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{args.version}.json"
    output_path.write_text(json.dumps(schema, indent=2))
    print(f"Schema written to {output_path}")


if __name__ == "__main__":
    main()
