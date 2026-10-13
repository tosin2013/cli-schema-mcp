"""CLI YAML config loader and validator."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml


@dataclass
class ObtainConfig:
    artifact_url: str
    checksum_url: str
    format: Literal["raw", "tar.gz", "zip"]
    binary: str
    version_url: str | None = None
    version_match: str | None = None


@dataclass
class CLIConfig:
    name: str
    display_name: str
    binary: str
    adapter: Literal["cobra", "help-parser", "custom"]
    versions: list[str]
    version_command: str
    version_parse: str
    upstream_repo: str = ""
    maintainers: list[str] = field(default_factory=list)
    # help-parser only
    help_flag: str = "--help"
    flag_regex: str = r"^\s+(--[\w-]+(?:,\s*-\w)?)\s+(.+)$"
    subcommand_regex: str = r"^\s{2}([\w-]+)\s+(.+)$"
    # custom adapter only
    extraction_script: str = ""
    obtain: ObtainConfig | None = None


_VALID_FORMATS = {"raw", "tar.gz", "zip"}


def _parse_obtain(raw: dict, path: Path) -> ObtainConfig:
    """Parse and validate the obtain block."""
    required = {"artifact_url", "checksum_url", "format", "binary"}
    missing = required - set(raw.keys())
    if missing:
        raise ValueError(f"obtain block in {path} missing required fields: {missing}")

    fmt = raw["format"]
    if fmt not in _VALID_FORMATS:
        raise ValueError(f"obtain.format must be one of {_VALID_FORMATS}, got {fmt!r} in {path}")

    version_url = raw.get("version_url")
    version_match = raw.get("version_match")

    if bool(version_url) != bool(version_match):
        raise ValueError(
            f"obtain.version_url and obtain.version_match must both be present or both absent in {path}"
        )

    if version_match:
        try:
            compiled = re.compile(version_match)
        except re.error as exc:
            raise ValueError(f"obtain.version_match is not a valid regex in {path}: {exc}") from exc
        if compiled.groups < 1:
            raise ValueError(
                f"obtain.version_match must contain exactly one capture group in {path}"
            )

    artifact_url = raw["artifact_url"]
    checksum_url = raw["checksum_url"]
    for field_name, url in (("artifact_url", artifact_url), ("checksum_url", checksum_url)):
        if "{version}" not in url and "{resolved}" not in url:
            raise ValueError(
                f"obtain.{field_name} must contain {{version}} or {{resolved}} in {path}"
            )

    return ObtainConfig(
        artifact_url=artifact_url,
        checksum_url=checksum_url,
        format=fmt,
        binary=raw["binary"],
        version_url=version_url or None,
        version_match=version_match or None,
    )


def load_cli_config(path: Path) -> CLIConfig:
    """Load and validate a CLI YAML config file."""
    data = yaml.safe_load(path.read_text())
    required = {"name", "binary", "adapter", "versions", "version_command", "version_parse"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Missing required fields in {path}: {missing}")

    obtain_raw = data.get("obtain")
    obtain = _parse_obtain(obtain_raw, path) if obtain_raw is not None else None

    known_fields = set(CLIConfig.__dataclass_fields__) - {"obtain"}
    kwargs = {k: v for k, v in data.items() if k in known_fields}
    kwargs["obtain"] = obtain
    return CLIConfig(**kwargs)


def load_all_configs(clis_dir: Path) -> list[CLIConfig]:
    """Load all CLI configs from a directory."""
    return [load_cli_config(p) for p in sorted(clis_dir.glob("*.yaml"))]
