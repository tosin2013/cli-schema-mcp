"""Tests for schema registry path resolution and version matching."""

import json
from pathlib import Path
from unittest.mock import patch

import cli_schema_mcp.src.schema_registry as reg
from cli_schema_mcp.src.schema_registry import (
    get_subcommand_node,
    list_tools,
    load_schema,
    resolve_version,
)

SAMPLE = {
    "name": "oc",
    "flags": [],
    "subcommands": [
        {
            "name": "rollout",
            "flags": [],
            "subcommands": [{"name": "restart", "flags": [], "subcommands": []}],
        }
    ],
}


def test_relative_schema_path_is_anchored_to_repo_root(tmp_path, monkeypatch):
    """A relative SCHEMA_REGISTRY_PATH does not follow the process CWD."""
    monkeypatch.setattr(reg, "_SCHEMAS_DIR", None)
    monkeypatch.chdir(tmp_path)
    with patch("cli_schema_mcp.src.settings.settings.SCHEMA_REGISTRY_PATH", "schemas"):
        assert reg._schemas_dir() == reg.repo_root() / "schemas"


def test_absolute_schema_path_is_used_as_given(monkeypatch):
    """An absolute SCHEMA_REGISTRY_PATH is not rewritten."""
    monkeypatch.setattr(reg, "_SCHEMAS_DIR", None)
    with patch(
        "cli_schema_mcp.src.settings.settings.SCHEMA_REGISTRY_PATH", "/var/schemas"
    ):
        assert reg._schemas_dir() == Path("/var/schemas")


def test_schema_dir_override_wins(tmp_path, monkeypatch):
    """Patching _SCHEMAS_DIR takes precedence over settings."""
    monkeypatch.setattr(reg, "_SCHEMAS_DIR", tmp_path)
    with patch(
        "cli_schema_mcp.src.settings.settings.SCHEMA_REGISTRY_PATH", "/var/schemas"
    ):
        assert reg._schemas_dir() == tmp_path


def test_clis_dir_anchored_when_cwd_changes(tmp_path, monkeypatch):
    """detect_version reads clis/ from the repo root, not the CWD."""
    import cli_schema_mcp.src.tools.detect_version_tool as detect

    monkeypatch.setattr(detect, "_CLIS_DIR", None)
    monkeypatch.chdir(tmp_path)
    assert detect._clis_dir() == reg.repo_root() / "clis"


def test_list_tools_skips_files_and_empty_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SCHEMAS_DIR", tmp_path)
    (tmp_path / "notes.txt").write_text("ignore")
    (tmp_path / "empty").mkdir()
    (tmp_path / "oc").mkdir()
    (tmp_path / "oc" / "4.22.json").write_text("{}")
    (tmp_path / "oc" / "4.18.json").write_text("{}")

    tools = list_tools()
    assert tools == {"oc": ["4.18", "4.22"]}


def test_list_tools_missing_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SCHEMAS_DIR", tmp_path / "missing")
    assert list_tools() == {}


def test_resolve_version_exact_minor_eus_and_latest(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SCHEMAS_DIR", tmp_path)
    oc = tmp_path / "oc"
    oc.mkdir()
    for version in ("4.18", "4.19", "4.20", "4.21", "4.22"):
        (oc / f"{version}.json").write_text("{}")
    tkn = tmp_path / "tkn"
    tkn.mkdir()
    (tkn / "0.36.json").write_text("{}")
    (tkn / "0.37.json").write_text("{}")

    assert resolve_version("missing", "1.0") is None
    assert resolve_version("oc", "4.22") == "4.22"
    assert resolve_version("oc", "4.22.1") == "4.22"
    assert resolve_version("oc", "4.23") == "4.22"
    assert resolve_version("oc", None) == "4.22"
    assert resolve_version("tkn", "0.37.0-rc1") == "0.37"
    assert resolve_version("tkn", "9.9.9") == "0.37"
    assert resolve_version("tkn", None) == "0.37"


def test_load_schema_missing_invalid_and_cache_isolation(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SCHEMAS_DIR", tmp_path)
    reg.load_schema.cache_clear()
    assert load_schema("oc", "4.22") is None

    oc = tmp_path / "oc"
    oc.mkdir()
    (oc / "bad.json").write_text("{")
    assert load_schema("oc", "bad") is None

    (oc / "4.22.json").write_text(json.dumps(SAMPLE))
    loaded = load_schema("oc", "4.22")
    assert loaded is not None
    assert loaded["name"] == "oc"

    other = tmp_path / "other"
    monkeypatch.setattr(reg, "_SCHEMAS_DIR", other)
    (other / "oc").mkdir(parents=True)
    (other / "oc" / "4.22.json").write_text(json.dumps({**SAMPLE, "name": "other-oc"}))
    again = load_schema("oc", "4.22")
    assert again is not None
    assert again["name"] == "other-oc"


def test_get_subcommand_node_walks_and_skips_binary_name():
    assert get_subcommand_node(SAMPLE, "rollout restart")["name"] == "restart"
    assert get_subcommand_node(SAMPLE, "oc rollout")["name"] == "rollout"
    assert get_subcommand_node(SAMPLE, "rollout missing") is None
    assert get_subcommand_node(SAMPLE, "oc")["name"] == "oc"
