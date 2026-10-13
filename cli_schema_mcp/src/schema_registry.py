"""Schema registry loader and version resolver for cli-schema-mcp."""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from cli_schema_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()

# Test override. None means resolve from settings at call time.
_SCHEMAS_DIR: Path | None = None


def repo_root() -> Path:
    """Directory that contains the cli_schema_mcp package and the schemas/ tree."""
    return Path(__file__).resolve().parents[2]


def _schemas_dir() -> Path:
    """Schema directory, read on each call so import-time CWD is not frozen."""
    if _SCHEMAS_DIR is not None:
        return Path(_SCHEMAS_DIR)
    from cli_schema_mcp.src.settings import settings

    configured = Path(settings.SCHEMA_REGISTRY_PATH)
    if configured.is_absolute():
        return configured
    return repo_root() / configured


def list_tools() -> dict[str, list[str]]:
    """Return all tools and their available schema versions."""
    base = _schemas_dir()
    result: dict[str, list[str]] = {}
    if not base.exists():
        return result
    for tool_dir in sorted(base.iterdir()):
        if not tool_dir.is_dir():
            continue
        versions = sorted(p.stem for p in tool_dir.glob("*.json"))
        if versions:
            result[tool_dir.name] = versions
    return result


def resolve_version(tool: str, requested: str | None) -> str | None:
    """
    Resolve the best matching schema version for a tool.

    Precedence: exact match → major.minor match → EUS preference (OCP even minors)
    → latest available.
    """
    base = _schemas_dir() / tool
    if not base.exists():
        return None

    available = sorted(p.stem for p in base.glob("*.json"))
    if not available:
        return None

    if requested is None:
        return _prefer_eus(tool, available)

    # Exact match
    if requested in available:
        return requested

    # major.minor match: strip patch (e.g. "4.22.1" → "4.22")
    minor = re.match(r"^(\d+\.\d+)", requested)
    if minor:
        minor_str = minor.group(1)
        if minor_str in available:
            return minor_str

    # EUS or latest fallback
    return _prefer_eus(tool, available)


def _prefer_eus(tool: str, available: list[str]) -> str:
    """For oc, prefer even minor versions (EUS); otherwise return the latest."""
    if tool == "oc":
        eus = [v for v in available if _is_even_minor(v)]
        if eus:
            return eus[-1]
    return available[-1]


def _is_even_minor(version: str) -> bool:
    m = re.match(r"^\d+\.(\d+)", version)
    if m:
        return int(m.group(1)) % 2 == 0
    return False


@lru_cache(maxsize=64)
def _load_schema_cached(path_str: str, mtime_ns: int) -> dict[str, Any]:
    """Cache a parsed schema by absolute path and mtime."""
    del mtime_ns
    return json.loads(Path(path_str).read_text())


def load_schema(tool: str, version: str) -> dict[str, Any] | None:
    """Load and cache a schema JSON file."""
    path = _schemas_dir() / tool / f"{version}.json"
    if not path.is_file():
        logger.warning(f"Schema not found: {path}")
        return None
    try:
        return _load_schema_cached(str(path), path.stat().st_mtime_ns)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse schema {path}: {e}")
        return None


load_schema.cache_clear = _load_schema_cached.cache_clear  # type: ignore[attr-defined]


def get_subcommand_node(
    schema: dict[str, Any], command_path: str
) -> dict[str, Any] | None:
    """
    Traverse the schema tree along a space-separated command path.

    The root node represents the top-level command. Each step descends
    into the matching child by name.
    """
    parts = command_path.strip().split()
    # Skip the binary name if it matches the root
    node = schema
    root_name = node.get("name", "")
    start = 0
    if parts and parts[0] == root_name:
        start = 1

    for part in parts[start:]:
        children = node.get("subcommands", [])
        match = next((c for c in children if c.get("name") == part), None)
        if match is None:
            return None
        node = match
    return node
