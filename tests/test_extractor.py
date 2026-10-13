"""Tests for the schema extractor entry point and adapters."""

import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from extractor.adapters import cobra
from extractor.adapters.help_parser import _parse_flags, _parse_subcommands
from extractor.main import extract_custom, main

REPO = Path(__file__).resolve().parents[1]


def _write_custom_config(clis: Path, script: Path, version: str = "1.0") -> None:
    clis.mkdir(parents=True, exist_ok=True)
    (clis / "demo.yaml").write_text(
        dedent(
            f"""\
            name: demo
            display_name: Demo
            binary: demo
            adapter: custom
            versions:
              - "{version}"
            version_command: demo version
            version_parse: "{{version}}"
            extraction_script: "{script}"
            """
        )
    )


def test_extract_custom_returns_script_json(tmp_path):
    script = tmp_path / "extract.py"
    script.write_text(
        "import json, sys\n"
        "json.dump({'name': sys.argv[1], 'version': sys.argv[2], 'flags': [], 'subcommands': []}, sys.stdout)\n"
    )
    schema = extract_custom(str(script), "demo", "1.0")
    assert schema["name"] == "demo"
    assert schema["version"] == "1.0"


def test_extract_custom_rejects_failure_and_invalid_json(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("import sys\nsys.stderr.write('nope\\n')\nsys.exit(2)\n")
    with pytest.raises(RuntimeError, match="exited 2"):
        extract_custom(str(bad), "demo", "1.0")

    noisy = tmp_path / "noisy.py"
    noisy.write_text("print('not-json')\n")
    with pytest.raises(ValueError, match="did not return JSON"):
        extract_custom(str(noisy), "demo", "1.0")

    with pytest.raises(ValueError, match="extraction_script"):
        extract_custom("  ", "demo", "1.0")


def test_module_entrypoint_runs_custom_adapter(tmp_path, monkeypatch):
    script = tmp_path / "extract.py"
    script.write_text(
        "import json, sys\n"
        "json.dump({'name': sys.argv[1], 'version': sys.argv[2], 'flags': [], 'subcommands': []}, sys.stdout)\n"
    )
    clis = tmp_path / "clis"
    out = tmp_path / "schemas"
    _write_custom_config(clis, script)
    monkeypatch.setattr(
        sys,
        "argv",
        ["extractor", "demo", "1.0", "--clis-dir", str(clis), "--output", str(out)],
    )
    main()
    written = json.loads((out / "demo" / "1.0.json").read_text())
    assert written["version"] == "1.0"


def test_python_module_invocation(tmp_path):
    script = tmp_path / "extract.py"
    script.write_text(
        "import json, sys\n"
        "json.dump({'tool': sys.argv[1], 'version': sys.argv[2]}, sys.stdout)\n"
    )
    clis = tmp_path / "clis"
    out = tmp_path / "schemas"
    _write_custom_config(clis, script, version="0.38")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "extractor",
            "demo",
            "0.38",
            "--clis-dir",
            str(clis),
            "--output",
            str(out),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((out / "demo" / "0.38.json").read_text())["version"] == "0.38"


def test_cobra_help_parser_reads_kubectl_flag_blocks_and_command_sections():
    text = (
        "Basic Commands:\n"
        "  login             Log in to a server\n"
        "  rollout           Manage the rollout of a resource\n"
        "\n"
        "Options:\n"
        "    -f, --filename=[]:\n"
        "\tFilename, directory, or URL to files identifying the resource.\n"
        "\n"
        "    --selector='':\n"
        "\tSelector (label query) to filter on.\n"
        "\n"
        "    --dry-run='none':\n"
        "\tMust be none, server, or client.\n"
        "\n"
        "    --request-timeout='0':\n"
        "\tThe length of time to wait before giving up. Non-zero values should contain a corresponding time unit (e.g. 1s, 2m, 3h).\n"
    )
    names = cobra._parse_subcommands(text)
    assert names == ["login", "rollout"]
    flags = cobra._parse_help_flags(text)
    assert flags["--filename"]["shorthand"] == "-f"
    assert flags["--filename"]["type"] == "stringArray"
    assert flags["--selector"]["type"] == "string"
    assert flags["--dry-run"]["default"] == "none"
    assert flags["--request-timeout"]["type"] == "duration"
    assert "--force" not in flags


def test_cobra_completion_pairs_shorthand_and_skips_unknown_flags():
    items = [
        ("--selector", "Selector (label query) to filter on"),
        ("--filename", "Filename, directory, or URL"),
        ("-l", "Selector (label query) to filter on"),
        ("-f", "Filename, directory, or URL"),
    ]
    meta = {
        "--filename": {
            "name": "--filename",
            "shorthand": "-f",
            "type": "stringArray",
            "default": None,
            "description": "Filename, directory, or URL",
            "deprecated": False,
        }
    }
    flags = {flag["name"]: flag for flag in cobra._flags_from_completion(items, meta)}
    assert flags["--selector"]["shorthand"] == "-l"
    assert flags["--filename"]["type"] == "stringArray"
    assert "--force" not in flags


def test_help_parser_reads_podman_style_flags():
    text = dedent(
        """\
        Available Commands:
          build       Build an image
          help        Help about any command

        Options:
              --add-host strings                         Add a custom host-to-IP mapping (default [])
          -d, --detach                                   Run container in background
        """
    )
    regex = r"^\s+((?:-\w,\s+)?--[\w-]+)(?:\s+(\S+))?\s{2,}(.+)$"
    flags = {flag["name"]: flag for flag in _parse_flags(text, regex)}
    assert flags["--add-host"]["type"] == "stringArray"
    assert flags["--detach"]["shorthand"] == "-d"
    assert flags["--detach"]["type"] == "bool"
    sub_re = r"^\s{2}([\w-]+)\s{2,}(.+)$"
    assert _parse_subcommands(text, sub_re) == ["build"]
