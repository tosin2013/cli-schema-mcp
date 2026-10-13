"""Cobra adapter — extracts CLI schemas from Cobra completion and help output.

Prefers the binary's ``__complete`` API (structured command and flag lists, including
inherited flags). Falls back to parsing ``--help`` when completion is unavailable.
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

_MAX_NODES = 8000
_WORKERS = 8

_KUBE_FLAG = re.compile(r"^\s+(?:-(\w),\s+)?(--[\w.-]+)(?:=(.*))?:\s*$")
_COBRA_FLAG = re.compile(
    r"^\s+(?:-(\w),\s+)?(--[\w.-]+)(?:\s+(\S+))?\s{2,}(.*)$"
)
_COMMAND_SECTION = re.compile(
    r"^(?:Available Commands|.+Commands(?:\s*\([^)]*\))?):\s*$"
)
_SUBCOMMAND = re.compile(r"^\s{2,}([\w-]+)\s{2,}\S")
_DURATION = re.compile(r"^\d+(?:\.\d+)?(?:ns|us|µs|ms|s|m|h)$")


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return env


def _run(cmd: list[str], timeout: int = 20) -> tuple[str, str, int]:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_env(),
    )
    return result.stdout or "", result.stderr or "", result.returncode


def _completion_items(binary: str, args: list[str]) -> list[tuple[str, str]] | None:
    """Return completion rows, or None when the binary has no __complete command."""
    try:
        stdout, stderr, _ = _run([binary, "__complete", *args])
    except subprocess.TimeoutExpired:
        return None
    # Cobra prints completion rows and a ":N" directive on stdout. The
    # human-readable "Completion ended" line is on stderr.
    if not re.search(r"(?m)^:\d+\s*$", stdout) and "Completion ended with directive" not in stderr:
        return None
    items: list[tuple[str, str]] = []
    for line in stdout.splitlines():
        if line.startswith(":"):
            break
        if line.startswith("Completion ended") or line.startswith("["):
            continue
        if "\t" in line:
            name, desc = line.split("\t", 1)
            items.append((name.strip(), desc.strip()))
        elif line.strip():
            items.append((line.strip(), ""))
    return items


def _parse_kube_default(raw: str | None) -> tuple[str, str | None]:
    """Map a kubectl/oc ``=value`` token to (type, default)."""
    if raw is None:
        return "string", None
    value = raw.strip()
    if value == "[]":
        return "stringArray", None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
        if value == "":
            return "string", None
    if value in {"true", "false"}:
        return "bool", value
    if re.fullmatch(r"-?\d+", value):
        return "int", value
    if _DURATION.fullmatch(value):
        return "duration", value
    return "string", value or None


def _parse_help_flags(help_text: str) -> dict[str, dict[str, Any]]:
    """Parse flag metadata from --help text. Keyed by long flag name."""
    lines = help_text.splitlines()
    meta: dict[str, dict[str, Any]] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        kube = _KUBE_FLAG.match(line)
        cobra = None if kube else _COBRA_FLAG.match(line)
        if kube is None and cobra is None:
            index += 1
            continue
        if kube is not None:
            shorthand, name, default_raw = kube.group(1), kube.group(2), kube.group(3)
            desc_lines: list[str] = []
            index += 1
            while index < len(lines):
                nxt = lines[index]
                if not nxt.strip():
                    break
                if _KUBE_FLAG.match(nxt) or _COBRA_FLAG.match(nxt):
                    break
                indent = len(nxt) - len(nxt.lstrip(" \t"))
                if nxt.startswith("\t") or indent >= 8:
                    desc_lines.append(nxt.strip())
                    index += 1
                    continue
                break
            description = " ".join(desc_lines).strip()
            ftype, default = _parse_kube_default(default_raw)
        else:
            assert cobra is not None
            shorthand = cobra.group(1)
            name = cobra.group(2)
            type_token = (cobra.group(3) or "").lower()
            description = (cobra.group(4) or "").strip()
            ftype = {
                "string": "string",
                "strings": "stringArray",
                "stringarray": "stringArray",
                "int": "int",
                "bool": "bool",
                "duration": "duration",
            }.get(type_token, "bool" if not type_token else "string")
            default_match = re.search(r"\(default (.+?)\)", description)
            default = default_match.group(1).strip("'\"") if default_match else None
            index += 1
        lowered = description.lower()
        if "can be repeated" in lowered:
            ftype = "stringArray"
        elif "time unit" in lowered or "duration" in lowered:
            ftype = "duration"
        elif lowered.startswith("if true") or lowered.startswith("if false"):
            if ftype == "string":
                ftype = "bool"
        meta[name] = {
            "name": name,
            "shorthand": f"-{shorthand}" if shorthand else None,
            "type": ftype,
            "default": default,
            "description": description,
            "deprecated": "DEPRECATED" in description.upper(),
        }
    return meta


def _parse_subcommands(help_text: str) -> list[str]:
    names: list[str] = []
    in_section = False
    for line in help_text.splitlines():
        if _COMMAND_SECTION.match(line):
            in_section = True
            continue
        if not in_section:
            continue
        if not line.strip() or re.match(r"^\S", line):
            in_section = False
            continue
        match = _SUBCOMMAND.match(line)
        if match and match.group(1) != "help":
            names.append(match.group(1))
    return names


def _infer_type(description: str, default: str | None) -> str:
    lowered = description.lower()
    if "can be repeated" in lowered:
        return "stringArray"
    if lowered.startswith("if true") or lowered.startswith("if false"):
        return "bool"
    if default in {"true", "false"}:
        return "bool"
    if default and re.fullmatch(r"-?\d+", default):
        return "int"
    if default and _DURATION.fullmatch(default):
        return "duration"
    return "string"


def _flags_from_completion(
    items: list[tuple[str, str]],
    help_meta: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    longs = [(name, desc) for name, desc in items if name.startswith("--")]
    shorts = [
        (name, desc)
        for name, desc in items
        if name.startswith("-") and not name.startswith("--")
    ]
    by_desc: dict[str, list[str]] = {}
    for name, desc in longs:
        by_desc.setdefault(desc, []).append(name)
    short_for: dict[str, str] = {}
    for short, desc in shorts:
        owners = by_desc.get(desc, [])
        if len(owners) == 1:
            short_for[owners[0]] = short

    flags: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name, desc in longs:
        if name in seen:
            continue
        seen.add(name)
        meta = help_meta.get(name, {})
        description = meta.get("description") or desc
        default = meta.get("default")
        ftype = meta.get("type") or _infer_type(description, default)
        flags.append(
            {
                "name": name,
                "shorthand": meta.get("shorthand") or short_for.get(name),
                "type": ftype,
                "default": default,
                "description": description,
                "deprecated": bool(meta.get("deprecated"))
                or "DEPRECATED" in description.upper(),
            }
        )
    return flags


def _node(name: str, flags: list[dict[str, Any]], subcommands: list[dict[str, Any]]) -> dict[str, Any]:
    return {"name": name, "flags": flags, "subcommands": subcommands}


class _Budget:
    """Shared cap on extracted command nodes."""

    def __init__(self) -> None:
        self._nodes = 0
        self._lock = threading.Lock()

    def take(self) -> bool:
        with self._lock:
            if self._nodes >= _MAX_NODES:
                return False
            self._nodes += 1
            return True


def _help_text(binary: str, path: list[str]) -> str:
    try:
        stdout, stderr, _ = _run([binary, *path, "--help"])
    except subprocess.TimeoutExpired:
        return ""
    return stdout + "\n" + stderr


def _global_flag_meta(binary: str) -> dict[str, dict[str, Any]]:
    meta: dict[str, dict[str, Any]] = {}
    for args in ([binary, "options"], [binary, "--help"]):
        try:
            stdout, stderr, _ = _run(args)
        except (subprocess.TimeoutExpired, OSError):
            continue
        parsed = _parse_help_flags(stdout + "\n" + stderr)
        for name, flag in parsed.items():
            meta.setdefault(name, flag)
    return meta


def _extract_help_tree(
    binary: str,
    path: list[str],
    seen: set[tuple[str, ...]],
    budget: _Budget,
) -> dict[str, Any]:
    key = tuple(path)
    name = path[-1] if path else binary
    if key in seen or not budget.take():
        return _node(name, [], [])
    seen.add(key)
    text = _help_text(binary, path)
    flags = list(_parse_help_flags(text).values())
    children = []
    for sub in _parse_subcommands(text):
        children.append(_extract_help_tree(binary, [*path, sub], seen, budget))
    return _node(name, flags, children)


def _extract_complete_tree(
    binary: str,
    path: list[str],
    global_meta: dict[str, dict[str, Any]],
    seen: set[tuple[str, ...]],
    budget: _Budget,
    parallel: bool,
) -> dict[str, Any]:
    key = tuple(path)
    name = path[-1] if path else binary
    if key in seen or not budget.take():
        return _node(name, [], [])
    branch_seen = seen | {key}

    sub_items = _completion_items(binary, [*path, ""])
    flag_items = _completion_items(binary, [*path, "-"])
    if sub_items is None and flag_items is None and not path:
        return _extract_help_tree(binary, path, set(branch_seen), budget)

    sub_names: list[str] = []
    for sub, _desc in sub_items or []:
        if not sub or sub.startswith("-") or sub == "help":
            continue
        if sub not in sub_names:
            sub_names.append(sub)

    local_meta = _parse_help_flags(_help_text(binary, path))
    merged = dict(global_meta)
    merged.update(local_meta)
    if flag_items is None:
        flags = list(local_meta.values())
    else:
        flags = _flags_from_completion(flag_items, merged)

    def child(sub: str) -> dict[str, Any]:
        return _extract_complete_tree(
            binary,
            [*path, sub],
            global_meta,
            branch_seen,
            budget,
            parallel=False,
        )

    if parallel and len(sub_names) > 1:
        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            children = list(pool.map(child, sub_names))
    else:
        children = [child(sub) for sub in sub_names]
    return _node(name, flags, children)


def extract(binary: str, version: str) -> dict[str, Any]:
    """Extract the full schema for a Cobra CLI binary."""
    budget = _Budget()
    probe = _completion_items(binary, [""])
    if probe is None:
        schema = _extract_help_tree(binary, [], set(), budget)
    else:
        schema = _extract_complete_tree(
            binary, [], _global_flag_meta(binary), set(), budget, parallel=True
        )
    schema["name"] = binary
    schema["version"] = version
    return schema
