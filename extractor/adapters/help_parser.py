"""Help-parser adapter — extracts CLI schemas from --help output using configurable regex."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Any

from extractor.cli_config import CLIConfig

_MAX_NODES = 8000
_TYPE_WORDS = {
    "string": "string",
    "strings": "stringArray",
    "stringarray": "stringArray",
    "strslice": "stringArray",
    "stringslice": "stringArray",
    "int": "int",
    "int32": "int",
    "int64": "int",
    "uint": "int",
    "uint32": "int",
    "uint64": "int",
    "bool": "bool",
    "boolean": "bool",
    "duration": "duration",
    "float": "string",
    "float32": "string",
    "float64": "string",
}


def _run(cmd: list[str], timeout: int = 20) -> str:
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        print(f"Warning: timed out running {' '.join(cmd)}", file=sys.stderr)
        return ""
    return (result.stdout or "") + (result.stderr or "")


def _flag_type(type_word: str | None) -> str:
    if not type_word:
        return "bool"
    return _TYPE_WORDS.get(type_word.lower(), "string")


def _parse_flags(help_text: str, flag_regex: str) -> list[dict[str, Any]]:
    flags = []
    seen: set[str] = set()
    pattern = re.compile(flag_regex, re.MULTILINE)
    for match in pattern.finditer(help_text):
        groups = match.groups()
        raw = groups[0] or ""
        type_word = None
        desc = ""
        if (
            len(groups) >= 3
            and groups[1]
            and str(groups[1]).startswith("--")
            and "--" not in raw
        ):
            raw = f"{raw},{groups[1]}"
            desc = (groups[2] or "").strip()
        elif len(groups) >= 3 and "--" in raw:
            type_word = groups[1]
            desc = (groups[2] or "").strip()
        elif len(groups) >= 2:
            desc = (groups[1] or "").strip()

        parts = [part.strip() for part in raw.split(",")]
        long = next((part for part in parts if part.startswith("--")), raw)
        short = next(
            (
                part
                for part in parts
                if part.startswith("-") and not part.startswith("--")
            ),
            None,
        )
        long_name, inline_default = _split_default(long.strip())
        name_bits = long_name.split()
        if len(name_bits) > 1 and name_bits[0].startswith("--"):
            long_name = name_bits[0]
            type_word = type_word or name_bits[1]
        if not long_name.startswith("--") or long_name in seen:
            continue
        seen.add(long_name)
        if short:
            short = short.rstrip(",")
            if not short.startswith("-"):
                short = f"-{short}"
        default_match = re.search(r"\(default (.+?)\)", desc)
        default = (
            default_match.group(1).strip("'\"") if default_match else inline_default
        )
        flags.append(
            {
                "name": long_name,
                "shorthand": short,
                "type": _flag_type(type_word),
                "default": default,
                "description": desc,
                "deprecated": "DEPRECATED" in desc.upper(),
            }
        )
    return flags


def _split_default(token: str) -> tuple[str, str | None]:
    if "=" not in token:
        return token, None
    name, default = token.split("=", 1)
    default = default.strip("'\"")
    return name, default or None


_SUBCOMMAND_SECTION = re.compile(
    r"^(?:Available Commands|SUBCOMMANDS?|[A-Z\s]*Commands?):\s*$"
)


def _commands_section(help_text: str) -> str:
    lines: list[str] = []
    in_section = False
    for line in help_text.splitlines():
        if _SUBCOMMAND_SECTION.match(line):
            in_section = True
            continue
        if not in_section:
            continue
        if line.strip() and not line.startswith((" ", "\t")):
            break
        lines.append(line)
    return "\n".join(lines) if lines else help_text


def _parse_subcommands(help_text: str, subcommand_regex: str) -> list[str]:
    pattern = re.compile(subcommand_regex, re.MULTILINE)
    names: list[str] = []
    for match in pattern.finditer(_commands_section(help_text)):
        name = match.group(1)
        if name != "help" and name not in names:
            names.append(name)
    return names


def _extract_subcommand(
    config: CLIConfig,
    path: list[str],
    seen: set[tuple[str, ...]],
) -> dict[str, Any]:
    key = tuple(path)
    name = path[-1] if path else config.binary
    if key in seen or len(seen) >= _MAX_NODES:
        return {"name": name, "flags": [], "subcommands": []}
    seen.add(key)

    try:
        help_text = _run([config.binary, *path, config.help_flag])
    except OSError as exc:
        print(
            f"Warning: failed to run {config.binary} {' '.join(path)}: {exc}",
            file=sys.stderr,
        )
        help_text = ""

    flags = _parse_flags(help_text, config.flag_regex)
    subcommands = []
    for sub in _parse_subcommands(help_text, config.subcommand_regex):
        subcommands.append(_extract_subcommand(config, [*path, sub], seen))

    return {"name": name, "flags": flags, "subcommands": subcommands}


def extract(config: CLIConfig, version: str) -> dict[str, Any]:
    """Extract the full schema for a CLI using help-parser adapter."""
    schema = _extract_subcommand(config, [], set())
    schema["name"] = config.binary
    schema["version"] = version
    return schema
