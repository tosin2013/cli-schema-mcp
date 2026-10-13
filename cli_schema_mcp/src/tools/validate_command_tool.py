"""MCP tool: validate_command — validate a fully-formed CLI command string against the schema."""

import re
from typing import Any

from cli_schema_mcp.src.schema_registry import (
    load_schema,
    resolve_version,
)
from cli_schema_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()

_FLAG_RE = re.compile(r"--?([\w-]+)(?:=\S*)?")


def _parse_flags_from_string(command_string: str) -> list[str]:
    """Extract flag names (without values) from a command string."""
    return [m.group(0).split("=")[0] for m in _FLAG_RE.finditer(command_string)]


def _find_subcommand_path(
    schema: dict[str, Any], tokens: list[str]
) -> tuple[dict[str, Any] | None, str]:
    """
    Walk the schema tree greedily along non-flag tokens to find the deepest
    matching subcommand node. Returns (node, path_string).
    """
    node = schema
    path_parts: list[str] = []
    root_name = schema.get("name", "")

    for token in tokens:
        if token.startswith("-"):
            break
        if not path_parts and token == root_name:
            continue
        children = node.get("subcommands", [])
        match = next((c for c in children if c.get("name") == token), None)
        if match is None:
            break
        node = match
        path_parts.append(token)

    return node, " ".join(path_parts)


def validate_command(
    tool: str, version: str | None, command_string: str
) -> dict[str, Any]:
    """
    TOOL_NAME=validate_command
    DISPLAY_NAME=Validate CLI Command
    USECASE=Validate a fully-formed CLI command string against the versioned schema before
    executing it. Use in autonomous agent workflows to catch hallucinated flags before they run.
    INSTRUCTIONS=1. Pass the complete command string including the binary name, subcommands,
    and all flags. 2. If valid=false, do not execute the command — revise it using the errors
    list. 3. Call get_flags to find the correct replacement flags.
    INPUT_DESCRIPTION=tool (str): CLI name. version (str|None): version or None for latest.
    command_string (str): Full command, e.g. 'oc rollout restart deployment/myapp --force'.
    OUTPUT_DESCRIPTION=Dictionary with status, valid (bool), errors (list of str describing
    each invalid flag), tool, version, matched_version, command_string.
    EXAMPLES=validate_command('oc', '4.22', 'oc rollout restart deployment/myapp --force'),
    validate_command('kubectl', '1.33', 'kubectl apply -f manifest.yaml --server-side')
    PREREQUISITES=Schemas must be present. Call list_supported() to verify availability.
    RELATED_TOOLS=get_flags, list_subcommands, detect_version

    Validate a CLI command string against the versioned schema.

    Args:
        tool: CLI tool name.
        version: Semver version string or None for latest.
        command_string: Full command string to validate.

    Returns:
        Dictionary with valid bool, errors list, and metadata.
    """
    try:
        if not command_string or not command_string.strip():
            return {
                "status": "error",
                "tool": tool,
                "version": version,
                "command_string": command_string,
                "error": "empty command string",
                "message": "empty command string",
            }

        matched = resolve_version(tool, version)
        if matched is None:
            return {
                "status": "error",
                "tool": tool,
                "version": version,
                "command_string": command_string,
                "error": f"No schema found for tool '{tool}'.",
                "message": "Tool or version not found in registry",
            }

        schema = load_schema(tool, matched)
        if schema is None:
            return {
                "status": "error",
                "tool": tool,
                "version": matched,
                "command_string": command_string,
                "error": f"Schema file for {tool} {matched} could not be loaded.",
                "message": "Schema load failure",
            }

        tokens = command_string.strip().split()
        node, path = _find_subcommand_path(schema, tokens)

        valid_flag_names = {f.get("name") for f in node.get("flags", [])}  # type: ignore[union-attr]
        # Also include shorthands
        for f in node.get("flags", []):  # type: ignore[union-attr]
            if f.get("shorthand"):
                valid_flag_names.add(f["shorthand"])

        used_flags = _parse_flags_from_string(command_string)
        errors = [
            f"{flag} is not a valid flag for '{tool}{' ' + path if path else ''}' in version {matched}"
            for flag in used_flags
            if flag not in valid_flag_names
        ]

        context = f"'{tool} {path}'" if path else f"'{tool}'"
        logger.info(
            f"validate_command: {tool} {matched} '{command_string[:60]}' → valid={not errors}"
        )
        return {
            "status": "success",
            "tool": tool,
            "version": version,
            "matched_version": matched,
            "command_string": command_string,
            "subcommand_context": context,
            "valid": len(errors) == 0,
            "errors": errors,
            "message": "Command is valid"
            if not errors
            else f"{len(errors)} invalid flag(s) found",
        }

    except Exception as e:
        logger.error(f"Error in validate_command: {e}")
        return {
            "status": "error",
            "tool": tool,
            "version": version,
            "command_string": command_string,
            "error": str(e),
            "message": "Failed to validate command",
        }
