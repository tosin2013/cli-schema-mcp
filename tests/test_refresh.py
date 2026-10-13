"""Tests for extractor/refresh.py — change detection, publish, exit codes."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tar_gz(member_name: str, content: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name=member_name)
        info.size = len(content)
        tf.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def _make_registration(
    name: str, versions: list[str], obtain_url_token: str = "{version}"
) -> dict:
    return {
        "name": name,
        "display_name": name.upper(),
        "binary": name,
        "adapter": "cobra",
        "versions": versions,
        "version_command": f"{name} version",
        "version_parse": "{version}",
        "obtain": {
            "artifact_url": f"https://example.com/{obtain_url_token}/{name}.tar.gz",
            "checksum_url": f"https://example.com/{obtain_url_token}/sha256sum.txt",
            "format": "tar.gz",
            "binary": name,
        },
    }


def _write_registration(clis_dir: Path, name: str, data: dict) -> Path:
    path = clis_dir / f"{name}.yaml"
    path.write_text(yaml.dump(data))
    return path


def _write_catalog(schemas_dir: Path, tool: str, version: str, schema: dict) -> Path:
    d = schemas_dir / tool
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{version}.json"
    p.write_text(json.dumps(schema, indent=2))
    return p


def _fake_schema(tool: str, version: str) -> dict:
    return {
        "name": tool,
        "version": version,
        "flags": [],
        "subcommands": [{"name": "get", "flags": [], "subcommands": []}],
    }


# ---------------------------------------------------------------------------
# US1: Two-version registration publishes both catalogs only after both succeed
# ---------------------------------------------------------------------------


class TestUS1Publish:
    """A two-version registration publishes both catalogs; outside registrations stay identical."""

    def _run_refresh(
        self,
        base: str,
        head: str,
        clis_dir: Path,
        schemas_dir: Path,
        extra_args: list[str] | None = None,
    ) -> tuple[int, str]:
        """Invoke refresh.main() and capture stdout + exit code."""
        from extractor import refresh as refresh_mod
        import io as _io

        args = [
            "--base",
            base,
            "--head",
            head,
            "--clis-dir",
            str(clis_dir),
            "--schemas-dir",
            str(schemas_dir),
        ]
        if extra_args:
            args += extra_args

        captured = _io.StringIO()
        exit_code = 0
        with (
            patch("sys.argv", ["extractor.refresh"] + args),
            patch("sys.stdout", captured),
        ):
            try:
                refresh_mod.main()
            except SystemExit as e:
                exit_code = e.code if isinstance(e.code, int) else 0

        return exit_code, captured.getvalue()

    def test_two_version_registration_publishes_both(self, tmp_path):
        """All-or-nothing: both versions must succeed before any catalog is written."""
        clis_dir = tmp_path / "clis"
        schemas_dir = tmp_path / "schemas"
        clis_dir.mkdir()
        schemas_dir.mkdir()

        data = _make_registration("mytool", ["1.0", "2.0"])
        _write_registration(clis_dir, "mytool", data)

        schema_1 = _fake_schema("mytool", "1.0")
        schema_2 = _fake_schema("mytool", "2.0")

        artifact_1 = _make_tar_gz("mytool", b"#!/bin/sh\necho v1")
        artifact_2 = _make_tar_gz("mytool", b"#!/bin/sh\necho v2")
        digest_1 = hashlib.sha256(artifact_1).hexdigest()
        digest_2 = hashlib.sha256(artifact_2).hexdigest()

        def fake_fetch_bytes(url):
            if "1.0" in url:
                return artifact_1
            return artifact_2

        def fake_fetch_text(url):
            if "1.0" in url:
                return f"{digest_1}  mytool.tar.gz\n"
            return f"{digest_2}  mytool.tar.gz\n"

        changed = {"mytool": "A"}

        def fake_changed(*a, **kw):
            return changed

        def fake_read_versions(*a, **kw):
            return ["1.0", "2.0"]

        def fake_extract(binary_path, config, version):
            return _fake_schema(config.name, version)

        with (
            patch(
                "extractor.refresh._changed_registration_paths",
                side_effect=fake_changed,
            ),
            patch(
                "extractor.refresh._read_versions_at_revision",
                side_effect=fake_read_versions,
            ),
            patch("extractor.obtain._fetch_bytes", side_effect=fake_fetch_bytes),
            patch("extractor.obtain._fetch_text", side_effect=fake_fetch_text),
            patch("extractor.refresh._extract_schema", side_effect=fake_extract),
        ):
            exit_code, output = self._run_refresh(
                "HEAD~1", "HEAD", clis_dir, schemas_dir
            )

        assert exit_code == 0, f"expected exit 0, got {exit_code}. output: {output}"
        assert (schemas_dir / "mytool" / "1.0.json").exists()
        assert (schemas_dir / "mytool" / "2.0.json").exists()
        assert "published" in output

        v1_data = json.loads((schemas_dir / "mytool" / "1.0.json").read_text())
        assert v1_data["version"] == "1.0"

    def test_outside_registrations_stay_identical(self, tmp_path):
        """Catalogs for unchanged registrations must not be rewritten."""
        clis_dir = tmp_path / "clis"
        schemas_dir = tmp_path / "schemas"
        clis_dir.mkdir()
        schemas_dir.mkdir()

        # Write an existing catalog for an unchanged tool
        existing = _write_catalog(
            schemas_dir, "stable_tool", "3.0", _fake_schema("stable_tool", "3.0")
        )
        existing_mtime = existing.stat().st_mtime
        existing_content = existing.read_bytes()

        data = _make_registration("mytool", ["1.0"])
        _write_registration(clis_dir, "mytool", data)

        artifact = _make_tar_gz("mytool", b"#!/bin/sh\necho v1")
        digest = hashlib.sha256(artifact).hexdigest()

        with (
            patch(
                "extractor.refresh._changed_registration_paths",
                return_value={"mytool": "A"},
            ),
            patch("extractor.refresh._read_versions_at_revision", return_value=["1.0"]),
            patch("extractor.obtain._fetch_bytes", return_value=artifact),
            patch(
                "extractor.obtain._fetch_text",
                return_value=f"{digest}  mytool.tar.gz\n",
            ),
            patch(
                "extractor.refresh._extract_schema",
                return_value=_fake_schema("mytool", "1.0"),
            ),
        ):
            exit_code, _ = self._run_refresh("HEAD~1", "HEAD", clis_dir, schemas_dir)

        assert exit_code == 0
        # unchanged catalog is byte-identical
        assert existing.read_bytes() == existing_content


# ---------------------------------------------------------------------------
# US2: Incomplete catalogs are rejected (exit 2, diff list)
# ---------------------------------------------------------------------------


class TestUS2NoPush:
    def _run_no_push(self, clis_dir: Path, schemas_dir: Path) -> tuple[int, str]:
        from extractor import refresh as refresh_mod
        import io as _io

        args = [
            "--base",
            "HEAD~1",
            "--head",
            "HEAD",
            "--no-push",
            "--clis-dir",
            str(clis_dir),
            "--schemas-dir",
            str(schemas_dir),
        ]

        captured = _io.StringIO()
        exit_code = 0
        with (
            patch("sys.argv", ["extractor.refresh"] + args),
            patch("sys.stdout", captured),
        ):
            try:
                refresh_mod.main()
            except SystemExit as e:
                exit_code = e.code if isinstance(e.code, int) else 0

        return exit_code, captured.getvalue()

    def test_no_push_exits_2_when_catalogs_differ(self, tmp_path):
        clis_dir = tmp_path / "clis"
        schemas_dir = tmp_path / "schemas"
        clis_dir.mkdir()
        schemas_dir.mkdir()

        data = _make_registration("mytool", ["1.0"])
        _write_registration(clis_dir, "mytool", data)

        artifact = _make_tar_gz("mytool", b"#!/bin/sh\necho v1")
        digest = hashlib.sha256(artifact).hexdigest()
        new_schema = _fake_schema("mytool", "1.0")

        with (
            patch(
                "extractor.refresh._changed_registration_paths",
                return_value={"mytool": "A"},
            ),
            patch("extractor.refresh._read_versions_at_revision", return_value=["1.0"]),
            patch("extractor.obtain._fetch_bytes", return_value=artifact),
            patch(
                "extractor.obtain._fetch_text",
                return_value=f"{digest}  mytool.tar.gz\n",
            ),
            patch("extractor.refresh._extract_schema", return_value=new_schema),
        ):
            exit_code, output = self._run_no_push(clis_dir, schemas_dir)

        assert exit_code == 2, f"expected exit 2, got {exit_code}"
        assert "catalogs differ:" in output
        assert "not updated" in output
        # schemas/ must not be modified
        assert not (schemas_dir / "mytool").exists()

    def test_no_push_exits_0_when_catalogs_already_match(self, tmp_path):
        clis_dir = tmp_path / "clis"
        schemas_dir = tmp_path / "schemas"
        clis_dir.mkdir()
        schemas_dir.mkdir()

        schema = _fake_schema("mytool", "1.0")
        _write_catalog(schemas_dir, "mytool", "1.0", schema)

        data = _make_registration("mytool", ["1.0"])
        _write_registration(clis_dir, "mytool", data)

        artifact = _make_tar_gz("mytool", b"#!/bin/sh\necho v1")
        digest = hashlib.sha256(artifact).hexdigest()

        with (
            patch(
                "extractor.refresh._changed_registration_paths",
                return_value={"mytool": "A"},
            ),
            patch("extractor.refresh._read_versions_at_revision", return_value=["1.0"]),
            patch("extractor.obtain._fetch_bytes", return_value=artifact),
            patch(
                "extractor.obtain._fetch_text",
                return_value=f"{digest}  mytool.tar.gz\n",
            ),
            patch("extractor.refresh._extract_schema", return_value=schema),
        ):
            exit_code, output = self._run_no_push(clis_dir, schemas_dir)

        assert exit_code == 0
        assert "catalogs already match" in output


# ---------------------------------------------------------------------------
# US3: Removal stays in sync
# ---------------------------------------------------------------------------


class TestUS3Removal:
    def _run_refresh(
        self,
        base: str,
        clis_dir: Path,
        schemas_dir: Path,
        changed: dict,
        read_versions_base: list,
        read_versions_head: list,
    ) -> tuple[int, str]:
        import extractor.refresh as refresh_mod
        import io as _io

        # Snapshot inputs to avoid any closure/binding issues
        changed_snapshot = dict(changed)
        base_snapshot = str(base)
        rv_base = list(read_versions_base)
        rv_head = list(read_versions_head)

        args = [
            "--base",
            base_snapshot,
            "--head",
            "HEAD",
            "--clis-dir",
            str(clis_dir),
            "--schemas-dir",
            str(schemas_dir),
        ]

        def _changed_side_effect(*a, **kw):
            return changed_snapshot

        def _read_versions_side_effect(tool, revision, clis_dir_arg):
            if revision == base_snapshot:
                return rv_base
            return rv_head

        captured = _io.StringIO()
        exit_code = 0
        # Use patch.object to target the module object directly, avoiding sys.modules lookup issues
        with (
            patch("sys.argv", ["extractor.refresh"] + args),
            patch("sys.stdout", captured),
            patch.object(
                refresh_mod,
                "_changed_registration_paths",
                side_effect=_changed_side_effect,
            ),
            patch.object(
                refresh_mod,
                "_read_versions_at_revision",
                side_effect=_read_versions_side_effect,
            ),
        ):
            try:
                refresh_mod.main()
            except SystemExit as e:
                exit_code = e.code if isinstance(e.code, int) else 0

        return exit_code, captured.getvalue()

    def test_removing_one_declared_version_deletes_its_catalog(self, tmp_path):
        """After removing version 2.0 from the registration, its catalog is deleted."""
        clis_dir = tmp_path / "clis"
        schemas_dir = tmp_path / "schemas"
        clis_dir.mkdir()
        schemas_dir.mkdir()

        # Pre-existing catalogs
        _write_catalog(schemas_dir, "mytool", "1.0", _fake_schema("mytool", "1.0"))
        _write_catalog(schemas_dir, "mytool", "2.0", _fake_schema("mytool", "2.0"))

        # Registration now only declares 1.0
        data = _make_registration("mytool", ["1.0"])
        _write_registration(clis_dir, "mytool", data)

        artifact = _make_tar_gz("mytool", b"#!/bin/sh\necho v1")
        digest = hashlib.sha256(artifact).hexdigest()
        new_schema = _fake_schema("mytool", "1.0")
        # same content as existing — so no diff for 1.0
        _write_catalog(schemas_dir, "mytool", "1.0", new_schema)

        with (
            patch("extractor.obtain._fetch_bytes", return_value=artifact),
            patch(
                "extractor.obtain._fetch_text",
                return_value=f"{digest}  mytool.tar.gz\n",
            ),
            patch("extractor.refresh._extract_schema", return_value=new_schema),
        ):
            exit_code, output = self._run_refresh(
                "HEAD~1",
                clis_dir,
                schemas_dir,
                changed={"mytool": "M"},
                read_versions_base=["1.0", "2.0"],
                read_versions_head=["1.0"],
            )

        assert exit_code == 0
        assert not (schemas_dir / "mytool" / "2.0.json").exists(), (
            "retired version should be deleted"
        )
        assert (schemas_dir / "mytool" / "1.0.json").exists(), (
            "remaining version should still exist"
        )

    def test_deleting_registration_removes_tool_directory(self, tmp_path):
        """Deleting the registration file removes schemas/<tool>/."""
        clis_dir = tmp_path / "clis"
        schemas_dir = tmp_path / "schemas"
        clis_dir.mkdir()
        schemas_dir.mkdir()

        _write_catalog(
            schemas_dir, "gone_tool", "1.0", _fake_schema("gone_tool", "1.0")
        )
        _write_catalog(
            schemas_dir, "gone_tool", "2.0", _fake_schema("gone_tool", "2.0")
        )

        # registration file is deleted (not in clis_dir)
        exit_code, output = self._run_refresh(
            "HEAD~1",
            clis_dir,
            schemas_dir,
            changed={"gone_tool": "D"},
            read_versions_base=["1.0", "2.0"],
            read_versions_head=[],
        )

        assert exit_code == 0
        assert not (schemas_dir / "gone_tool").exists(), (
            "tool directory should be removed"
        )
        assert "published" in output
