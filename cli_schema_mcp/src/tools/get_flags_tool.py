"""MCP tool: get_flags — return all valid flags for a CLI command path and version."""

from typing import Any

from cli_schema_mcp.src.schema_registry import get_subcommand_node, load_schema, resolve_version
from cli_schema_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()


def get_flags(tool: str, version: str | None, command: str) -> dict[str, Any]:
    """
    TOOL_NAME=get_flags
    DISPLAY_NAME=Get CLI Flags
    USECASE=Retrieve all valid flags for a specific CLI tool, version, and command path.
    Use this before generating any CLI command to ensure only valid flags are suggested.
    INSTRUCTIONS=1. Call with tool name (e.g. 'oc'), version (e.g. '4.22'), and command
    path (e.g. 'rollout restart'). 2. Use the returned flag list to constrain command
    generation — never suggest a flag that is not in this list. 3. Check 'deprecated' field
    before using a flag.
    INPUT_DESCRIPTION=tool (str): CLI tool name. version (str|None): semver version or None
    for latest. command (str): space-separated subcommand path, e.g. 'rollout restart'.
    OUTPUT_DESCRIPTION=Dictionary with status, tool, version, command, matched_version, and
    flags list. Each flag has name, type, shorthand, default, description, deprecated.
    EXAMPLES=get_flags('oc', '4.22', 'rollout restart'), get_flags('kubectl', None, 'apply')
    PREREQUISITES=Schemas must be present in the registry (schemas/<tool>/<version>.json).
    Call list_supported() first to verify the tool and version are available.
    RELATED_TOOLS=list_subcommands, validate_command, list_supported, detect_version

    Return all valid flags for a given CLI tool, version, and subcommand path.

    Args:
        tool: CLI tool name (e.g. 'oc', 'kubectl', 'helm').
        version: Semver version string or None for latest/best-match.
        command: Space-separated subcommand path (e.g. 'rollout restart').

    Returns:
        Dictionary containing the flag list and metadata.
    """
    try:
        matched = resolve_version(tool, version)
        if matched is None:
            return {
                "status": "error",
                "tool": tool,
                "version": version,
                "error": f"No schema found for tool '{tool}'. Call list_supported() to see available tools.",
                "message": "Tool or version not found in registry",
            }

        schema = load_schema(tool, matched)
        if schema is None:
            return {
                "status": "error",
                "tool": tool,
                "version": version,
                "matched_version": matched,
                "error": f"Schema file for {tool} {matched} could not be loaded.",
                "message": "Schema load failure",
            }

        node = get_subcommand_node(schema, command)
        if node is None:
            return {
                "status": "error",
                "tool": tool,
                "version": matched,
                "command": command,
                "error": f"Subcommand '{command}' not found in {tool} {matched} schema.",
                "message": "Subcommand not found",
            }

        flags = node.get("flags", [])
        logger.info(f"get_flags: {tool} {matched} '{command}' → {len(flags)} flags")
        return {
            "status": "success",
            "tool": tool,
            "version": version,
            "matched_version": matched,
            "command": command,
            "flags": flags,
            "message": f"Found {len(flags)} flags for '{tool} {command}' (schema version {matched})",
        }

    except Exception as e:
        logger.error(f"Error in get_flags: {e}")
        return {
            "status": "error",
            "tool": tool,
            "version": version,
            "command": command,
            "error": str(e),
            "message": "Failed to retrieve flags",
        }
