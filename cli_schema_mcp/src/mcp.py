"""cli-schema-mcp MCP server implementation."""

from fastmcp import FastMCP

from cli_schema_mcp.src.settings import settings
from cli_schema_mcp.src.tools.detect_version_tool import detect_version
from cli_schema_mcp.src.tools.get_flags_tool import get_flags
from cli_schema_mcp.src.tools.list_subcommands_tool import list_subcommands
from cli_schema_mcp.src.tools.list_supported_tool import list_supported
from cli_schema_mcp.src.tools.validate_command_tool import validate_command
from cli_schema_mcp.utils.pylogger import (
    force_reconfigure_all_loggers,
    get_python_logger,
)

logger = get_python_logger()


class CliSchemaMCPServer:
    """CLI schema MCP server — tools-first architecture.

    Exposes version-pinned CLI flag schemas via MCP so AI agents can generate
    accurate CLI commands without flag hallucination.
    """

    def __init__(self):
        """Initialize the server and register all schema tools."""
        try:
            self.mcp = FastMCP("cli-schema-mcp")
            force_reconfigure_all_loggers(settings.PYTHON_LOG_LEVEL)
            self._register_mcp_tools()
            logger.info("cli-schema-mcp server initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize cli-schema-mcp server: {e}")
            raise

    def _register_mcp_tools(self) -> None:
        """Register all five CLI schema tools with FastMCP."""
        self.mcp.tool()(list_supported)
        self.mcp.tool()(get_flags)
        self.mcp.tool()(list_subcommands)
        self.mcp.tool()(validate_command)
        self.mcp.tool()(detect_version)
