"""MCP tool: get_download_info — return download URLs for a CLI version from its registration."""

import platform
from pathlib import Path
from typing import Any

import yaml

from cli_schema_mcp.src.schema_registry import repo_root
from cli_schema_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()

_CLIS_DIR: Path | None = None

# Mapping from Python platform.machine() values → canonical arch strings used in URLs
_MACHINE_TO_ARCH: dict[str, str] = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
    "ppc64le": "ppc64le",
    "s390x": "s390x",
}

# URL patterns that indicate amd64 and their per-arch replacements.
# Checked in order; first match wins.
_ARCH_SUBSTITUTIONS: list[tuple[str, dict[str, str]]] = [
    # helm, tkn, virtctl: "linux-amd64"
    (
        "linux-amd64",
        {"arm64": "linux-arm64", "ppc64le": "linux-ppc64le", "s390x": "linux-s390x"},
    ),
    # kustomize, podman: "linux_amd64"
    (
        "linux_amd64",
        {"arm64": "linux_arm64", "ppc64le": "linux_ppc64le", "s390x": "linux_s390x"},
    ),
    # kubectl: "linux/amd64/"
    (
        "linux/amd64/",
        {"arm64": "linux/arm64/", "ppc64le": "linux/ppc64le/", "s390x": "linux/s390x/"},
    ),
    # tkn archive member: "Linux_x86_64"
    (
        "Linux_x86_64",
        {"arm64": "Linux_aarch64", "ppc64le": "Linux_ppc64le", "s390x": "Linux_s390x"},
    ),
    # oc, others: "-linux.tar.gz" (no arch suffix = amd64 default)
    (
        "-linux.tar.gz",
        {
            "arm64": "-linux-arm64.tar.gz",
            "ppc64le": "-linux-ppc64le.tar.gz",
            "s390x": "-linux-s390x.tar.gz",
        },
    ),
    # raw binary ending with "-linux" (virtctl style)
    (
        "-linux-amd64",
        {"arm64": "-linux-arm64", "ppc64le": "-linux-ppc64le", "s390x": "-linux-s390x"},
    ),
]


def _apply_arch(url: str, arch: str) -> tuple[str, bool]:
    """Return (url_for_arch, was_substituted)."""
    if arch == "amd64":
        return url, True  # default URLs are already amd64
    for pattern, replacements in _ARCH_SUBSTITUTIONS:
        if pattern in url and arch in replacements:
            return url.replace(pattern, replacements[arch], 1), True
    return url, False


def _clis_dir() -> Path:
    if _CLIS_DIR is not None:
        return Path(_CLIS_DIR)
    return repo_root() / "clis"


def get_download_info(
    tool: str,
    version: str | None = None,
    arch: str | None = None,
    os: str | None = None,
) -> dict[str, Any]:
    """
    TOOL_NAME=get_download_info
    DISPLAY_NAME=Get CLI Download Info
    USECASE=Return download URLs and install guidance for a CLI tool so the agent can
    tell the user where to get it, or download it programmatically in a container. Use
    when detect_version returns status=binary_not_found, or when the user asks how to
    install a supported CLI. Pass arch and os for containerized or cross-arch deployments
    so the correct binary variant is returned. The server never downloads or installs
    anything — this is purely informational.
    INSTRUCTIONS=1. Call with the tool name and optionally version, arch, and os.
    2. Detect arch automatically via platform.machine() if not provided by the user.
    3. Present artifact_url and checksum_url as the download location.
    4. For non-interactive agents: download via HTTP client (not shell), verify SHA-256,
    install to a path your deployment controls (e.g. a mounted volume). Never assume
    sudo is available. 5. If arch_substituted=false, the arch variant could not be
    determined — fall back to the default URL or check upstream_repo manually.
    INPUT_DESCRIPTION=tool (str): CLI name matching a clis/<tool>.yaml registration.
    version (str|None): Minor version string (e.g. '4.22'). If omitted, returns all versions.
    arch (str|None): Target CPU architecture — 'amd64', 'arm64', 'ppc64le', 's390x'.
    If omitted, auto-detected from the host running the MCP server.
    os (str|None): Target OS — 'linux', 'darwin', 'windows'. Currently informational only.
    OUTPUT_DESCRIPTION=Dictionary with status, tool, arch, versions list, and for each version:
    artifact_url (arch-specific when possible), checksum_url, format, binary, arch_substituted
    (true if the URL was adapted for the requested arch), and optional version_url/version_match.
    EXAMPLES=get_download_info('oc', '4.22'), get_download_info('kubectl', arch='arm64'),
    get_download_info('helm', '4.3', arch='arm64', os='linux')
    PREREQUISITES=None — works without any CLI installed. Reads only clis/*.yaml.
    RELATED_TOOLS=detect_version, list_supported

    Return download URLs and install guidance for a CLI tool.

    Args:
        tool: CLI tool name matching a clis/<tool>.yaml registration.
        version: Minor version string (e.g. '4.22'). None returns all declared versions.
        arch: Target CPU architecture ('amd64', 'arm64', 'ppc64le', 's390x').
              Defaults to the host running the MCP server.
        os: Target OS ('linux', 'darwin', 'windows'). Currently informational.

    Returns:
        Dictionary with download URLs, format, and install guidance.
    """
    try:
        # Resolve arch — default to MCP server host if not specified
        resolved_arch = _MACHINE_TO_ARCH.get(
            (arch or platform.machine()).lower(), arch or platform.machine()
        )
        resolved_os = (os or "linux").lower()

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
            return {
                "status": "success",
                "tool": tool,
                "arch": resolved_arch,
                "os": resolved_os,
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
            artifact_base = artifact_url_template.replace("{version}", v)
            checksum_base = checksum_url_template.replace("{version}", v)

            artifact, art_substituted = _apply_arch(artifact_base, resolved_arch)
            checksum, chk_substituted = _apply_arch(checksum_base, resolved_arch)

            entry: dict[str, Any] = {
                "version": v,
                "artifact_url": artifact,
                "format": fmt,
                "binary": binary,
                "arch": resolved_arch,
                "arch_substituted": art_substituted,
            }
            if not art_substituted and resolved_arch != "amd64":
                entry["arch_warning"] = (
                    f"Could not determine the {resolved_arch} variant of the artifact URL. "
                    f"The default (likely amd64) URL is shown. Check {config.get('upstream_repo', 'upstream')} for the correct URL."
                )
            if checksum and not skip_checksum:
                entry["checksum_url"] = checksum
            if skip_checksum:
                entry["checksum_note"] = (
                    "This CLI does not publish a checksum file. Verify the download via the upstream release page."
                )
            if version_url_template:
                entry["patch_resolution"] = {
                    "version_url": version_url_template.replace("{version}", v),
                    "version_match": version_match,
                    "note": "{resolved} in artifact_url is the patch tag returned by version_url matching version_match.",
                }
            version_entries.append(entry)

        install_notes = (
            "Download the artifact, verify the SHA-256 checksum (if provided), and place "
            "the binary in your PATH. In non-interactive/containerized environments: "
            "download via HTTP client (not shell), verify checksum programmatically, and "
            "install to a path your deployment controls (e.g. a mounted volume). "
            "Never assume sudo or a writable root filesystem is available."
        )
        if skip_checksum:
            install_notes = (
                "Download the artifact from the release page and place the binary in your PATH. "
                "No checksum file is published by this project — verify via the upstream release page."
            )

        logger.info(
            f"get_download_info: {tool} arch={resolved_arch} versions={target_versions}"
        )
        return {
            "status": "success",
            "tool": tool,
            "arch": resolved_arch,
            "os": resolved_os,
            "upstream_repo": config.get("upstream_repo", ""),
            "versions": version_entries,
            "install_notes": install_notes,
            "message": f"Download info for {tool} {', '.join(target_versions)} [{resolved_arch}/{resolved_os}]",
        }

    except Exception as e:
        logger.error(f"Error in get_download_info: {e}")
        return {
            "status": "error",
            "tool": tool,
            "error": str(e),
            "message": "Failed to retrieve download info",
        }
