"""MCP tool: get_download_info — return download URLs for a CLI version from its registration."""

from pathlib import Path
from typing import Any

import yaml

from cli_schema_mcp.src.schema_registry import repo_root
from cli_schema_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()

_CLIS_DIR: Path | None = None


def _clis_dir() -> Path:
    if _CLIS_DIR is not None:
        return Path(_CLIS_DIR)
    return repo_root() / "clis"


def get_download_info(tool: str, version: str | None = None) -> dict[str, Any]:
    """
    TOOL_NAME=get_download_info
    DISPLAY_NAME=Get CLI Download Info
    USECASE=Return download URLs and install guidance for a CLI tool so the agent can
    tell the user where to get it. Use when detect_version returns status=binary_not_found,
    or when the user asks how to install a supported CLI. The server never downloads or
    installs anything — this is purely informational for the user or calling environment.
    INSTRUCTIONS=1. Call with the tool name and optionally a version string. 2. Present
    artifact_url and checksum_url to the user as the download location. 3. If skip_checksum
    is true, note that this CLI does not publish checksums — verify the download via the
    upstream release page. 4. version_url and version_match explain how CI resolves the patch
    tag from the declared minor version.
    INPUT_DESCRIPTION=tool (str): CLI name matching a clis/<tool>.yaml registration.
    version (str|None): Minor version string (e.g. '4.22'). If omitted, returns info for
    all declared versions.
    OUTPUT_DESCRIPTION=Dictionary with status, tool, versions list, and for each version:
    artifact_url (with tokens resolved to the version string), checksum_url, format, binary,
    and optional version_url / version_match for patch resolution. Also includes upstream_repo
    and install_notes.
    EXAMPLES=get_download_info('oc', '4.22'), get_download_info('kubectl'), get_download_info('virtctl', '1.9')
    PREREQUISITES=None — works without any CLI installed. The server reads only clis/*.yaml.
    RELATED_TOOLS=detect_version, list_supported

    Return download URLs and install guidance for a CLI tool.

    Args:
        tool: CLI tool name matching a clis/<tool>.yaml registration.
        version: Minor version string (e.g. '4.22'). None returns all declared versions.

    Returns:
        Dictionary with download URLs, format, and install guidance.
    """
    try:
        path = _clis_dir() / f"{tool}.yaml"
        if not path.exists():
            return {
                "status": "error",
                "tool": tool,
                "error": f"No registration found at clis/{tool}.yaml. Call list_supported() to see available tools.",
                "message": "Tool not registered",
            }

        config = yaml.safe_load(path.read_text())
        obtain = config.get("obtain")

        declared_versions: list[str] = config.get("versions", [])
        if version is not None and version not in declared_versions:
            return {
                "status": "error",
                "tool": tool,
                "version": version,
                "error": f"Version '{version}' is not declared. Available: {declared_versions}",
                "message": "Version not found",
            }

        target_versions = [version] if version else declared_versions

        if obtain is None:
            # System package — no automated download
            return {
                "status": "success",
                "tool": tool,
                "versions": target_versions,
                "install_method": "system_package",
                "install_notes": (
                    f"'{tool}' is a system package with no automated download URL. "
                    f"Install via your package manager (e.g. dnf install {tool}) or see "
                    f"{config.get('upstream_repo', 'the upstream project')} for instructions."
                ),
                "upstream_repo": config.get("upstream_repo", ""),
            }

        artifact_url_template = obtain.get("artifact_url", "")
        checksum_url_template = obtain.get("checksum_url", "")
        fmt = obtain.get("format", "")
        binary = obtain.get("binary", tool)
        version_url_template = obtain.get("version_url")
        version_match = obtain.get("version_match")
        skip_checksum = obtain.get("skip_checksum", False)

        version_entries = []
        for v in target_versions:
            # Fill {version} token; {resolved} requires network lookup so show the template
            artifact = artifact_url_template.replace("{version}", v)
            checksum = checksum_url_template.replace("{version}", v)
            entry: dict[str, Any] = {
                "version": v,
                "artifact_url": artifact,
                "format": fmt,
                "binary": binary,
            }
            if checksum and not skip_checksum:
                entry["checksum_url"] = checksum
            if skip_checksum:
                entry["checksum_note"] = "This CLI does not publish a checksum file. Verify the download via the upstream release page."
            if version_url_template:
                entry["patch_resolution"] = {
                    "version_url": version_url_template.replace("{version}", v),
                    "version_match": version_match,
                    "note": "{resolved} in artifact_url is the patch tag returned by version_url matching version_match.",
                }
            version_entries.append(entry)

        upstream = config.get("upstream_repo", "")
        install_notes = f"Download the artifact, verify the checksum (if provided), and place the binary in your PATH."
        if skip_checksum:
            install_notes = f"Download the artifact from the release page and place the binary in your PATH. No checksum file is published by this project."

        logger.info(f"get_download_info: {tool} versions={target_versions}")
        return {
            "status": "success",
            "tool": tool,
            "upstream_repo": upstream,
            "versions": version_entries,
            "install_notes": install_notes,
            "message": f"Download info for {tool} {', '.join(target_versions)}",
        }

    except Exception as e:
        logger.error(f"Error in get_download_info: {e}")
        return {
            "status": "error",
            "tool": tool,
            "error": str(e),
            "message": "Failed to retrieve download info",
        }
