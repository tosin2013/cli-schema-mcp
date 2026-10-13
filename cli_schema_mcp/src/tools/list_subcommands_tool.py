"""MCP tool: list_subcommands — return valid subcommands for a CLI and version."""

from typing import Any

from cli_schema_mcp.src.schema_registry import get_subcommand_node, load_schema, resolve_version
from cli_schema_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()


def list_subcommands(
    tool: str, version: str | None, parent: str | None = None
) -> dict[str, Any]:
    """
    TOOL_NAME=list_subcommands
    DISPLAY_NAME=List CLI Subcommands
    USECASE=Discover valid subcommands for a CLI tool at a given version, optionally under a
    parent command. Use before generating a command to ensure the subcommand exists.
    INSTRUCTIONS=1. Call with tool, version, and optional parent (e.g. 'rollout'). 2. If parent
    is omitted, top-level commands are returned. 3. Use the result to confirm a subcommand exists
    before calling get_flags on it.
    INPUT_DESCRIPTION=tool (str): CLI name. version (str|None): version or None for latest.
    parent (str|None): parent subcommand path, e.g. 'rollout'. None returns top-level commands.
    OUTPUT_DESCRIPTION=Dictionary with status, tool, version, parent, matched_version, and
    subcommands list (list of strings).
    EXAMPLES=list_subcommands('oc', '4.22', 'rollout'), list_subcommands('kubectl', None)
    PREREQUISITES=Schemas must be present. Call list_supported() to verify availability.
    RELATED_TOOLS=get_flags, validate_command, list_supported

    Return valid subcommand names under a parent, or top-level commands if parent is None.

    Args:
        tool: CLI tool name.
        version: Semver version string or None for latest.
        parent: Parent subcommand path, e.g. 'rollout'. None for top-level.

    Returns:
        Dictionary with subcommand list and metadata.
    """
    try:
        matched = resolve_version(tool, version)
        if matched is None:
            return {
                "status": "error",
                "tool": tool,
                "version": version,
                "error": f"No schema found for tool '{tool}'.",
                "message": "Tool or version not found in registry",
            }

        schema = load_schema(tool, matched)
        if schema is None:
            return {
                "status": "error",
                "tool": tool,
                "version": matched,
                "error": f"Schema file for {tool} {matched} could not be loaded.",
                "message": "Schema load failure",
            }

        if parent:
            node = get_subcommand_node(schema, parent)
            if node is None:
                return {
                    "status": "error",
                    "tool": tool,
                    "version": matched,
                    "parent": parent,
                    "error": f"Subcommand '{parent}' not found in {tool} {matched}.",
                    "message": "Subcommand not found",
                }
        else:
            node = schema

        subcommands = [c.get("name", "") for c in node.get("subcommands", [])]
        logger.info(f"list_subcommands: {tool} {matched} parent='{parent}' → {len(subcommands)} subcommands")
        return {
            "status": "success",
            "tool": tool,
            "version": version,
            "matched_version": matched,
            "parent": parent,
            "subcommands": subcommands,
            "message": f"Found {len(subcommands)} subcommands under '{parent or tool}'",
        }

    except Exception as e:
        logger.error(f"Error in list_subcommands: {e}")
        return {
            "status": "error",
            "tool": tool,
            "version": version,
            "parent": parent,
            "error": str(e),
            "message": "Failed to list subcommands",
        }
