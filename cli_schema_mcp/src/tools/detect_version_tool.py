"""MCP tool: detect_version — detect the installed version of a CLI tool."""

import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from cli_schema_mcp.src.schema_registry import repo_root, resolve_version
from cli_schema_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()

# Test override. None means resolve next to the repo root at call time.
_CLIS_DIR: Path | None = None


def _clis_dir() -> Path:
    """CLI config directory, resolved when called so CWD at import does not stick."""
    if _CLIS_DIR is not None:
        return Path(_CLIS_DIR)
    return repo_root() / "clis"


def _load_cli_config(tool: str) -> dict[str, Any] | None:
    path = _clis_dir() / f"{tool}.yaml"
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text())
    except Exception:
        return None


def detect_version(tool: str) -> dict[str, Any]:
    """
    TOOL_NAME=detect_version
    DISPLAY_NAME=Detect CLI Version
    USECASE=Detect the installed version of a CLI tool in the current environment and map it
    to the nearest schema version in the registry. Use at the start of a session to auto-select
    the correct schema version without requiring the user to specify one.
    INSTRUCTIONS=1. Call with the tool name. 2. Use matched_schema as the version argument for
    subsequent get_flags, list_subcommands, and validate_command calls. 3. If status=error,
    either the binary is not installed or the version could not be parsed — fall back to
    list_supported() and ask the user which version to use.
    INPUT_DESCRIPTION=tool (str): CLI tool name, e.g. 'oc', 'kubectl', 'helm'.
    OUTPUT_DESCRIPTION=Dictionary with status, tool, version (raw detected string),
    matched_schema (schema version to use), and message.
    EXAMPLES=detect_version('oc'), detect_version('kubectl'), detect_version('helm')
    PREREQUISITES=The CLI binary must be installed and available in PATH. The tool must be
    listed in clis/<tool>.yaml for version parsing.
    RELATED_TOOLS=list_supported, get_flags, validate_command

    Detect the installed version of a CLI tool and resolve to the nearest schema version.

    Args:
        tool: CLI tool name.

    Returns:
        Dictionary with detected version and matched schema version.
    """
    try:
        config = _load_cli_config(tool)
        if config is None:
            return {
                "status": "error",
                "tool": tool,
                "error": f"No CLI config found at clis/{tool}.yaml. Call list_supported() to see configured tools.",
                "message": "CLI config not found",
            }

        version_cmd = config.get("version_command", f"{tool} version")
        version_parse = config.get("version_parse", r"v?(\d+\.\d+(?:\.\d+)?)")

        try:
            result = subprocess.run(
                version_cmd.split(),
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = result.stdout + result.stderr
        except FileNotFoundError:
            return {
                "status": "error",
                "tool": tool,
                "error": f"Binary '{tool}' not found in PATH. Ensure it is installed.",
                "message": "Binary not found",
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "tool": tool,
                "error": f"Version command timed out: {version_cmd}",
                "message": "Version detection timed out",
            }

        # Extract version string using configured pattern
        pattern = version_parse.replace("{version}", r"([\d.]+(?:-[\w.]+)?)")
        match = re.search(pattern, output)
        if not match:
            return {
                "status": "error",
                "tool": tool,
                "error": f"Could not parse version from output: {output[:200]}",
                "message": "Version parse failure",
            }

        raw_version = match.group(1) if match.lastindex else match.group(0)
        matched = resolve_version(tool, raw_version)

        logger.info(f"detect_version: {tool} detected={raw_version} matched={matched}")
        return {
            "status": "success",
            "tool": tool,
            "version": raw_version,
            "matched_schema": matched or "unknown",
            "message": f"Detected {tool} {raw_version}, using schema {matched or 'none'}",
        }

    except Exception as e:
        logger.error(f"Error in detect_version: {e}")
        return {
            "status": "error",
            "tool": tool,
            "error": str(e),
            "message": "Failed to detect version",
        }
