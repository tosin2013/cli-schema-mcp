"""Tests for cli-schema-mcp MCP tools."""

import json
from contextlib import contextmanager
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SCHEMA = {
    "name": "oc",
    "version": "4.22",
    "flags": [],
    "subcommands": [
        {
            "name": "rollout",
            "flags": [
                {
                    "name": "--namespace",
                    "shorthand": "-n",
                    "type": "string",
                    "default": None,
                    "description": "Namespace",
                    "deprecated": False,
                }
            ],
            "subcommands": [
                {
                    "name": "restart",
                    "flags": [
                        {
                            "name": "--dry-run",
                            "shorthand": None,
                            "type": "string",
                            "default": "none",
                            "description": "Must be none, server, or client",
                            "deprecated": False,
                        },
                        {
                            "name": "--filename",
                            "shorthand": "-f",
                            "type": "stringArray",
                            "default": None,
                            "description": "Filename",
                            "deprecated": False,
                        },
                        {
                            "name": "--selector",
                            "shorthand": "-l",
                            "type": "string",
                            "default": None,
                            "description": "Selector",
                            "deprecated": False,
                        },
                        {
                            "name": "--timeout",
                            "shorthand": None,
                            "type": "duration",
                            "default": "0s",
                            "description": "Timeout",
                            "deprecated": False,
                        },
                    ],
                    "subcommands": [],
                },
                {
                    "name": "status",
                    "flags": [
                        {
                            "name": "--watch",
                            "shorthand": "-w",
                            "type": "bool",
                            "default": "false",
                            "description": "Watch",
                            "deprecated": False,
                        },
                    ],
                    "subcommands": [],
                },
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# TestListSupportedTool
# ---------------------------------------------------------------------------


class TestListSupportedTool:
    """Tests for list_supported()."""

    def test_returns_success_with_tools(self, tmp_path):
        """list_supported returns all tools and versions from the schemas directory."""
        (tmp_path / "oc").mkdir()
        (tmp_path / "oc" / "4.22.json").write_text("{}")
        (tmp_path / "kubectl").mkdir()
        (tmp_path / "kubectl" / "1.33.json").write_text("{}")

        with patch("cli_schema_mcp.src.schema_registry._SCHEMAS_DIR", tmp_path):
            # Clear lru_cache between tests
            import cli_schema_mcp.src.schema_registry as reg

            reg.load_schema.cache_clear()
            from cli_schema_mcp.src.tools.list_supported_tool import list_supported

            result = list_supported()

        assert result["status"] == "success"
        assert "oc" in result["tools"]
        assert "4.22" in result["tools"]["oc"]
        assert "kubectl" in result["tools"]
        assert result["total_tools"] == 2
        assert result["total_schemas"] == 2

    def test_returns_success_empty_registry(self, tmp_path):
        """list_supported returns empty tools dict when no schemas exist."""
        with patch("cli_schema_mcp.src.schema_registry._SCHEMAS_DIR", tmp_path):
            from cli_schema_mcp.src.tools.list_supported_tool import list_supported

            result = list_supported()

        assert result["status"] == "success"
        assert result["tools"] == {}
        assert result["total_tools"] == 0

    def test_returns_error_on_exception(self):
        """list_supported returns error dict on unexpected exception."""
        with patch(
            "cli_schema_mcp.src.tools.list_supported_tool.list_tools",
            side_effect=RuntimeError("boom"),
        ):
            from cli_schema_mcp.src.tools.list_supported_tool import list_supported

            result = list_supported()

        assert result["status"] == "error"
        assert "error" in result


# ---------------------------------------------------------------------------
# TestGetFlagsTool
# ---------------------------------------------------------------------------


class TestGetFlagsTool:
    """Tests for get_flags()."""

    @contextmanager
    def _patched_get_flags(self, schema, version_to_match="4.22"):
        """Patch registry functions for the duration of the get_flags call."""
        import cli_schema_mcp.src.schema_registry as reg

        reg.load_schema.cache_clear()
        with (
            patch(
                "cli_schema_mcp.src.tools.get_flags_tool.resolve_version",
                return_value=version_to_match,
            ),
            patch(
                "cli_schema_mcp.src.tools.get_flags_tool.load_schema",
                return_value=schema,
            ),
        ):
            from cli_schema_mcp.src.tools.get_flags_tool import get_flags

            yield get_flags

    def test_returns_flags_for_valid_command(self):
        """get_flags returns correct flags for oc rollout restart."""
        with self._patched_get_flags(SAMPLE_SCHEMA) as get_flags:
            result = get_flags("oc", "4.22", "rollout restart")

        assert result["status"] == "success"
        assert result["tool"] == "oc"
        assert result["matched_version"] == "4.22"
        flag_names = [f["name"] for f in result["flags"]]
        assert "--selector" in flag_names
        assert "--timeout" in flag_names
        assert "--dry-run" in flag_names
        assert "--force" not in flag_names  # critical: hallucinated flag must be absent

    def test_returns_error_for_missing_tool(self):
        """get_flags returns error when tool has no schema in registry."""
        with patch(
            "cli_schema_mcp.src.tools.get_flags_tool.resolve_version", return_value=None
        ):
            from cli_schema_mcp.src.tools.get_flags_tool import get_flags

            result = get_flags("nonexistent", "1.0", "version")

        assert result["status"] == "error"
        assert "error" in result

    def test_returns_error_for_nonexistent_subcommand(self):
        """get_flags returns error when subcommand path doesn't exist."""
        with self._patched_get_flags(SAMPLE_SCHEMA) as get_flags:
            result = get_flags("oc", "4.22", "rollout nonexistent")

        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    def test_returns_error_on_schema_load_failure(self):
        """get_flags returns error when schema file cannot be loaded."""
        with (
            patch(
                "cli_schema_mcp.src.tools.get_flags_tool.resolve_version",
                return_value="4.22",
            ),
            patch(
                "cli_schema_mcp.src.tools.get_flags_tool.load_schema", return_value=None
            ),
        ):
            from cli_schema_mcp.src.tools.get_flags_tool import get_flags

            result = get_flags("oc", "4.22", "rollout restart")

        assert result["status"] == "error"

    def test_result_always_contains_status(self):
        """get_flags always returns a dict with a status field."""
        with self._patched_get_flags(SAMPLE_SCHEMA) as get_flags:
            result = get_flags("oc", "4.22", "rollout restart")
        assert "status" in result

    def test_version_fallback_returns_nearest_schema(self, tmp_path):
        """get_flags('oc', '4.23', ...) returns 4.22 flags and matched_version."""
        import cli_schema_mcp.src.schema_registry as reg

        oc_dir = tmp_path / "oc"
        oc_dir.mkdir()
        (oc_dir / "4.22.json").write_text(json.dumps(SAMPLE_SCHEMA))
        reg.load_schema.cache_clear()
        with patch("cli_schema_mcp.src.schema_registry._SCHEMAS_DIR", tmp_path):
            from cli_schema_mcp.src.tools.get_flags_tool import get_flags

            result = get_flags("oc", "4.23", "rollout restart")

        assert result["status"] == "success"
        assert result["matched_version"] == "4.22"
        flag_names = [flag["name"] for flag in result["flags"]]
        assert "--selector" in flag_names
        assert "--timeout" in flag_names
        assert "--filename" in flag_names
        assert "--dry-run" in flag_names
        assert "--force" not in flag_names

    def test_prerelease_matches_minor_when_present(self, tmp_path):
        """0.37.0-rc1 resolves to the 0.37 schema when that file exists."""
        import cli_schema_mcp.src.schema_registry as reg

        tool_dir = tmp_path / "tkn"
        tool_dir.mkdir()
        schema = {
            "name": "tkn",
            "version": "0.37",
            "flags": [
                {
                    "name": "--kubeconfig",
                    "shorthand": None,
                    "type": "string",
                    "default": None,
                    "description": "kubeconfig",
                    "deprecated": False,
                }
            ],
            "subcommands": [],
        }
        (tool_dir / "0.36.json").write_text(json.dumps({**schema, "version": "0.36"}))
        (tool_dir / "0.37.json").write_text(json.dumps(schema))
        reg.load_schema.cache_clear()
        with patch("cli_schema_mcp.src.schema_registry._SCHEMAS_DIR", tmp_path):
            from cli_schema_mcp.src.tools.get_flags_tool import get_flags

            result = get_flags("tkn", "0.37.0-rc1", "tkn")

        assert result["status"] == "success"
        assert result["matched_version"] == "0.37"

    def test_prerelease_falls_back_to_latest_when_minor_missing(self, tmp_path):
        """A pre-release with no minor match falls back to the latest schema."""
        import cli_schema_mcp.src.schema_registry as reg

        tool_dir = tmp_path / "tkn"
        tool_dir.mkdir()
        schema = {
            "name": "tkn",
            "version": "0.36",
            "flags": [],
            "subcommands": [],
        }
        (tool_dir / "0.36.json").write_text(json.dumps(schema))
        reg.load_schema.cache_clear()
        with patch("cli_schema_mcp.src.schema_registry._SCHEMAS_DIR", tmp_path):
            from cli_schema_mcp.src.tools.get_flags_tool import get_flags

            result = get_flags("tkn", "0.37.0-rc1", "tkn")

        assert result["status"] == "success"
        assert result["matched_version"] == "0.36"


# ---------------------------------------------------------------------------
# TestListSubcommandsTool
# ---------------------------------------------------------------------------


class TestListSubcommandsTool:
    """Tests for list_subcommands()."""

    @contextmanager
    def _patched(self, schema, matched="4.22"):
        with (
            patch(
                "cli_schema_mcp.src.tools.list_subcommands_tool.resolve_version",
                return_value=matched,
            ),
            patch(
                "cli_schema_mcp.src.tools.list_subcommands_tool.load_schema",
                return_value=schema,
            ),
        ):
            from cli_schema_mcp.src.tools.list_subcommands_tool import list_subcommands

            yield list_subcommands

    def test_returns_top_level_subcommands(self):
        """list_subcommands with no parent returns top-level command names."""
        with self._patched(SAMPLE_SCHEMA) as fn:
            result = fn("oc", "4.22")

        assert result["status"] == "success"
        assert "rollout" in result["subcommands"]

    def test_returns_subcommands_under_parent(self):
        """list_subcommands returns correct children under 'rollout'."""
        with self._patched(SAMPLE_SCHEMA) as fn:
            result = fn("oc", "4.22", "rollout")

        assert result["status"] == "success"
        assert "restart" in result["subcommands"]
        assert "status" in result["subcommands"]

    def test_returns_error_for_missing_parent(self):
        """list_subcommands returns error when parent doesn't exist."""
        with self._patched(SAMPLE_SCHEMA) as fn:
            result = fn("oc", "4.22", "nonexistent-command")

        assert result["status"] == "error"

    def test_returns_error_for_missing_tool(self):
        """list_subcommands returns error when tool not in registry."""
        with patch(
            "cli_schema_mcp.src.tools.list_subcommands_tool.resolve_version",
            return_value=None,
        ):
            from cli_schema_mcp.src.tools.list_subcommands_tool import list_subcommands

            result = list_subcommands("ghost", None)

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# TestValidateCommandTool
# ---------------------------------------------------------------------------


class TestValidateCommandTool:
    """Tests for validate_command()."""

    @contextmanager
    def _patched(self, schema, matched="4.22"):
        with (
            patch(
                "cli_schema_mcp.src.tools.validate_command_tool.resolve_version",
                return_value=matched,
            ),
            patch(
                "cli_schema_mcp.src.tools.validate_command_tool.load_schema",
                return_value=schema,
            ),
        ):
            from cli_schema_mcp.src.tools.validate_command_tool import validate_command

            yield validate_command

    def test_valid_command_returns_valid_true(self):
        """validate_command returns valid=True for a command using only schema flags."""
        with self._patched(SAMPLE_SCHEMA) as fn:
            result = fn(
                "oc",
                "4.22",
                "oc rollout restart deployment/myapp --selector app=frontend",
            )

        assert result["status"] == "success"
        assert result["valid"] is True
        assert result["errors"] == []

    def test_hallucinated_flag_returns_valid_false(self):
        """validate_command returns valid=False and names --force as invalid."""
        with self._patched(SAMPLE_SCHEMA) as fn:
            result = fn("oc", "4.22", "oc rollout restart deployment/myapp --force")

        assert result["status"] == "success"
        assert result["valid"] is False
        assert len(result["errors"]) >= 1
        assert any("--force" in e for e in result["errors"])

    def test_multiple_invalid_flags_all_reported(self):
        """validate_command reports all invalid flags, not just the first."""
        with self._patched(SAMPLE_SCHEMA) as fn:
            result = fn(
                "oc", "4.22", "oc rollout restart deployment/myapp --force --delete"
            )

        assert result["valid"] is False
        assert len(result["errors"]) == 2

    def test_returns_error_for_missing_tool(self):
        """validate_command returns error dict when tool is not in registry."""
        with patch(
            "cli_schema_mcp.src.tools.validate_command_tool.resolve_version",
            return_value=None,
        ):
            from cli_schema_mcp.src.tools.validate_command_tool import validate_command

            result = validate_command("ghost", None, "ghost do something")

        assert result["status"] == "error"

    def test_result_always_has_status(self):
        """validate_command always returns a dict with a status field."""
        with self._patched(SAMPLE_SCHEMA) as fn:
            result = fn("oc", "4.22", "oc rollout restart")
        assert "status" in result

    def test_empty_command_string_is_rejected(self):
        """An empty command string returns a structured error and does not crash."""
        from cli_schema_mcp.src.tools.validate_command_tool import validate_command

        result = validate_command("oc", "4.22", "")
        assert result["status"] == "error"
        assert result["error"] == "empty command string"

    def test_whitespace_command_string_is_rejected(self):
        """A whitespace-only command string is treated as empty."""
        from cli_schema_mcp.src.tools.validate_command_tool import validate_command

        result = validate_command("oc", "4.22", "   \t  ")
        assert result["status"] == "error"
        assert result["error"] == "empty command string"

    def test_hyphenated_filename_not_flagged(self):
        """Hyphens inside positional args (filenames) are not treated as flags."""
        with self._patched(SAMPLE_SCHEMA) as fn:
            # -f is a valid flag; vector-tuning.yaml is a positional arg, not a flag
            result = fn("oc", "4.22", "oc rollout restart -f vector-tuning.yaml")
        assert result["status"] == "success"
        assert result["valid"] is True
        assert result["errors"] == []

    def test_hyphenated_flag_value_not_flagged(self):
        """Hyphens inside flag values are not treated as flags."""
        with self._patched(SAMPLE_SCHEMA) as fn:
            # --selector is valid; component=openshift-logging is its value, not a flag
            result = fn(
                "oc",
                "4.22",
                "oc rollout restart deployment/myapp --selector component=openshift-logging",
            )
        assert result["status"] == "success"
        assert result["valid"] is True
        assert result["errors"] == []

    def test_posix_double_dash_separator_not_flagged(self):
        """'--' is treated as end-of-flags separator, not an unknown flag."""
        with self._patched(SAMPLE_SCHEMA) as fn:
            # everything after -- is a literal subcommand; -- itself is not a flag
            result = fn(
                "oc", "4.22", "oc rollout restart deployment/myapp -- cat /var/log/file"
            )
        assert result["status"] == "success"
        assert result["valid"] is True
        assert not any(
            "--" in e and "not a valid flag" in e for e in result.get("errors", [])
        )

    def test_flag_with_equals_value_parsed_correctly(self):
        """Flags written as --flag=value still extract just --flag."""
        with self._patched(SAMPLE_SCHEMA) as fn:
            result = fn(
                "oc",
                "4.22",
                "oc rollout restart deployment/myapp --selector=app=frontend",
            )
        assert result["status"] == "success"
        assert result["valid"] is True

    def test_hyphenated_resource_name_before_double_dash(self):
        """A hyphenated resource name is not mis-parsed as a flag."""
        with self._patched(SAMPLE_SCHEMA) as fn:
            # vector-abc123 is a positional arg (resource name), not a flag
            result = fn("oc", "4.22", "oc rollout restart vector-abc123")
        assert result["status"] == "success"
        assert result["valid"] is True
        assert not any("abc123" in e for e in result.get("errors", []))


# ---------------------------------------------------------------------------
# TestDetectVersionTool
# ---------------------------------------------------------------------------


class TestDetectVersionTool:
    """Tests for detect_version()."""

    def test_returns_error_when_config_not_found(self, tmp_path):
        """detect_version returns error when CLI config YAML is missing."""
        with patch("cli_schema_mcp.src.tools.detect_version_tool._CLIS_DIR", tmp_path):
            from cli_schema_mcp.src.tools.detect_version_tool import detect_version

            result = detect_version("nonexistent")

        assert result["status"] == "error"
        assert "config" in result["error"].lower()

    def test_returns_error_when_binary_not_found(self, tmp_path):
        """detect_version returns error when binary is absent from PATH."""
        cfg = tmp_path / "fakecli.yaml"
        cfg.write_text(
            "name: fakecli\nbinary: fakecli\nversion_command: fakecli version\nversion_parse: 'v{version}'\nadapter: cobra\nversions: ['1.0']\n"
        )
        with patch("cli_schema_mcp.src.tools.detect_version_tool._CLIS_DIR", tmp_path):
            from cli_schema_mcp.src.tools.detect_version_tool import detect_version

            result = detect_version("fakecli")

        assert result["status"] == "error"
        assert (
            "not found" in result["error"].lower()
            or "error" in result["message"].lower()
        )

    def test_always_returns_dict_with_status(self, tmp_path):
        """detect_version always returns a dict with a status field."""
        with patch("cli_schema_mcp.src.tools.detect_version_tool._CLIS_DIR", tmp_path):
            from cli_schema_mcp.src.tools.detect_version_tool import detect_version

            result = detect_version("anything")

        assert "status" in result
