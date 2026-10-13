"""MCP tool: list_supported — return all CLI tools and versions in the schema registry."""

from typing import Any

from cli_schema_mcp.src.schema_registry import list_tools
from cli_schema_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()


def list_supported() -> dict[str, Any]:
    """
    TOOL_NAME=list_supported
    DISPLAY_NAME=List Supported CLI Tools
    USECASE=Discover which CLI tools and versions are available in the schema registry.
    Call this first to verify a tool/version is supported before calling other tools.
    INSTRUCTIONS=1. Call with no arguments. 2. Inspect the result to confirm your target
    tool and version are listed. 3. If the tool is missing, a schema has not been extracted
    for it yet — the registry only contains pre-built schemas.
    INPUT_DESCRIPTION=No parameters required.
    OUTPUT_DESCRIPTION=Dictionary with status, tools (dict mapping tool name to list of
    available schema versions), total_tools (int), total_schemas (int), and message.
    EXAMPLES=list_supported()
    PREREQUISITES=None — this is always the first call to make.
    RELATED_TOOLS=get_flags, list_subcommands, validate_command, detect_version

    Return all CLI tools and schema versions available in the registry.

    Returns:
        Dictionary with the complete tool/version registry.
    """
    try:
        tools = list_tools()
        total_schemas = sum(len(v) for v in tools.values())
        logger.info(f"list_supported: {len(tools)} tools, {total_schemas} schemas")
        return {
            "status": "success",
            "tools": tools,
            "total_tools": len(tools),
            "total_schemas": total_schemas,
            "message": f"Registry contains {len(tools)} tools and {total_schemas} schema versions",
        }
    except Exception as e:
        logger.error(f"Error in list_supported: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to list supported tools",
        }
