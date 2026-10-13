"""Tests for extractor/obtain.py — token fill, checksum, unpack."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from extractor.obtain import (
    ObtainInstruction,
    ObtainError,
    _fill_tokens,
    _verify_checksum,
    _extract_from_tar,
    _extract_from_zip,
    obtain,
    resolve_version,
)


# ---------------------------------------------------------------------------
# Token fill
# ---------------------------------------------------------------------------


class TestFillTokens:
    def test_version_replaced(self):
        assert (
            _fill_tokens("https://example.com/{version}/file", "1.31", "1.31.5")
            == "https://example.com/1.31/file"
        )

    def test_resolved_replaced(self):
        assert (
            _fill_tokens("https://example.com/{resolved}/file", "1.31", "v1.31.5")
            == "https://example.com/v1.31.5/file"
        )

    def test_both_tokens_replaced(self):
        result = _fill_tokens("url/{version}/{resolved}", "5.3", "5.3.2")
        assert result == "url/5.3/5.3.2"

    def test_no_tokens(self):
        assert (
            _fill_tokens("https://example.com/file", "1.0", "1.0.1")
            == "https://example.com/file"
        )


class TestResolveVersion:
    def test_no_version_url_returns_version(self):
        instr = ObtainInstruction(
            artifact_url="https://example.com/{version}/file",
            checksum_url="https://example.com/{version}/file.sha256",
            format="raw",
            binary="mybinary",
        )
        assert resolve_version(instr, "1.31") == "1.31"

    def test_version_url_fetches_and_matches(self):
        instr = ObtainInstruction(
            artifact_url="https://example.com/{resolved}/file",
            checksum_url="https://example.com/{resolved}/file.sha256",
            format="raw",
            binary="mybinary",
            version_url="https://example.com/stable-{version}.txt",
            version_match=r"v([\d.]+)",
        )
        with patch(
            "extractor.obtain._fetch_text", return_value="v1.31.5\n"
        ) as mock_fetch:
            result = resolve_version(instr, "1.31")
        assert result == "1.31.5"
        mock_fetch.assert_called_once_with("https://example.com/stable-1.31.txt")

    def test_version_url_no_match_raises(self):
        instr = ObtainInstruction(
            artifact_url="https://example.com/{resolved}/file",
            checksum_url="https://example.com/{resolved}/file.sha256",
            format="raw",
            binary="mybinary",
            version_url="https://example.com/stable.txt",
            version_match=r"NOPE([\d.]+)",
        )
        with patch("extractor.obtain._fetch_text", return_value="v1.31.5\n"):
            with pytest.raises(ObtainError, match="did not match"):
                resolve_version(instr, "1.31")


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------


class TestVerifyChecksum:
    def _digest(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def test_bare_64hex_matches(self):
        data = b"hello world"
        _verify_checksum(data, "file.bin", self._digest(data))

    def test_bare_64hex_mismatch_raises(self):
        data = b"hello world"
        wrong = "a" * 64
        with pytest.raises(ObtainError, match="mismatch"):
            _verify_checksum(data, "file.bin", wrong)

    def test_sha256sum_listing_matches(self):
        data = b"artifact content"
        listing = f"{self._digest(data)}  artifact.tar.gz\n"
        _verify_checksum(data, "artifact.tar.gz", listing)

    def test_sha256sum_listing_star_matches(self):
        data = b"artifact content"
        listing = f"{self._digest(data)} *artifact.tar.gz\n"
        _verify_checksum(data, "artifact.tar.gz", listing)

    def test_sha256sum_listing_wrong_file_raises(self):
        data = b"artifact content"
        listing = f"{self._digest(data)}  other.tar.gz\n"
        with pytest.raises(ObtainError, match="does not contain an entry"):
            _verify_checksum(data, "artifact.tar.gz", listing)

    def test_sha256sum_listing_mismatch_raises(self):
        data = b"artifact content"
        listing = f"{'b' * 64}  artifact.tar.gz\n"
        with pytest.raises(ObtainError, match="mismatch"):
            _verify_checksum(data, "artifact.tar.gz", listing)

    def test_empty_body_raises(self):
        with pytest.raises(ObtainError):
            _verify_checksum(b"data", "file", "")


# ---------------------------------------------------------------------------
# Unpack
# ---------------------------------------------------------------------------


class TestExtractFromTar:
    def _make_tar_gz(self, member_name: str, content: bytes) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            info = tarfile.TarInfo(name=member_name)
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))
        return buf.getvalue()

    def test_extracts_member(self, tmp_path):
        tar_data = self._make_tar_gz("bin/mybinary", b"#!/bin/sh\necho hi")
        dest = tmp_path / "mybinary"
        result = _extract_from_tar(tar_data, "bin/mybinary", dest)
        assert result == dest
        assert dest.read_bytes() == b"#!/bin/sh\necho hi"
        assert dest.stat().st_mode & stat.S_IXUSR

    def test_missing_member_raises(self, tmp_path):
        tar_data = self._make_tar_gz("other/file", b"data")
        dest = tmp_path / "mybinary"
        with pytest.raises(ObtainError, match="not found"):
            _extract_from_tar(tar_data, "bin/mybinary", dest)


class TestExtractFromZip:
    def _make_zip(self, member_name: str, content: bytes) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(member_name, content)
        return buf.getvalue()

    def test_extracts_member(self, tmp_path):
        zip_data = self._make_zip("bin/mybinary", b"#!/bin/sh\necho hi")
        dest = tmp_path / "mybinary"
        result = _extract_from_zip(zip_data, "bin/mybinary", dest)
        assert result == dest
        assert dest.read_bytes() == b"#!/bin/sh\necho hi"

    def test_missing_member_raises(self, tmp_path):
        zip_data = self._make_zip("other", b"data")
        dest = tmp_path / "mybinary"
        with pytest.raises(ObtainError, match="not found"):
            _extract_from_zip(zip_data, "bin/mybinary", dest)


# ---------------------------------------------------------------------------
# obtain() — full pipeline (mocked network)
# ---------------------------------------------------------------------------


class TestObtain:
    def _make_raw_artifact(self) -> bytes:
        return b"#!/bin/sh\necho kubectl"

    def _make_tar_gz(self, member: str, content: bytes) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            info = tarfile.TarInfo(name=member)
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))
        return buf.getvalue()

    def test_raw_format(self, tmp_path):
        artifact = self._make_raw_artifact()
        digest = hashlib.sha256(artifact).hexdigest()

        instr = ObtainInstruction(
            artifact_url="https://example.com/{version}/kubectl",
            checksum_url="https://example.com/{version}/kubectl.sha256",
            format="raw",
            binary="kubectl",
        )

        def fake_fetch_bytes(url):
            return artifact

        def fake_fetch_text(url):
            return digest

        with (
            patch("extractor.obtain._fetch_bytes", side_effect=fake_fetch_bytes),
            patch("extractor.obtain._fetch_text", side_effect=fake_fetch_text),
        ):
            result = obtain(instr, "1.31", tmp_path)

        assert result.name == "kubectl"
        assert result.read_bytes() == artifact

    def test_checksum_mismatch_does_not_unpack(self, tmp_path):
        artifact = self._make_tar_gz("oc", b"binary")
        instr = ObtainInstruction(
            artifact_url="https://example.com/{version}/oc.tar.gz",
            checksum_url="https://example.com/{version}/sha256sum.txt",
            format="tar.gz",
            binary="oc",
        )

        with (
            patch("extractor.obtain._fetch_bytes", return_value=artifact),
            patch("extractor.obtain._fetch_text", return_value="a" * 64),
        ):
            with pytest.raises(ObtainError, match="mismatch"):
                obtain(instr, "4.22", tmp_path)

        # dest dir should be empty or only the dir itself
        assert not list(tmp_path.iterdir()) or all(
            p.is_dir() for p in tmp_path.iterdir()
        )

    def test_missing_version_token_raises(self, tmp_path):
        instr = ObtainInstruction(
            artifact_url="https://example.com/static/oc.tar.gz",
            checksum_url="https://example.com/sha256sum.txt",
            format="tar.gz",
            binary="oc",
        )
        with pytest.raises(ObtainError, match="neither"):
            obtain(instr, "4.22", tmp_path)

    def test_tar_format_extracts(self, tmp_path):
        content = b"#!/bin/sh\necho oc"
        artifact = self._make_tar_gz("oc", content)
        digest = hashlib.sha256(artifact).hexdigest()

        instr = ObtainInstruction(
            artifact_url="https://example.com/{version}/openshift-client.tar.gz",
            checksum_url="https://example.com/{version}/sha256sum.txt",
            format="tar.gz",
            binary="oc",
        )

        listing = f"{digest}  openshift-client.tar.gz\n"

        with (
            patch("extractor.obtain._fetch_bytes", return_value=artifact),
            patch("extractor.obtain._fetch_text", return_value=listing),
        ):
            result = obtain(instr, "4.22", tmp_path)

        assert result.read_bytes() == content

    def test_catalog_with_no_commands_fails(self, tmp_path):
        """Simulate obtaining a binary that produces an empty catalog."""
        artifact = self._make_raw_artifact()
        digest = hashlib.sha256(artifact).hexdigest()

        instr = ObtainInstruction(
            artifact_url="https://example.com/{version}/binary",
            checksum_url="https://example.com/{version}/sha256",
            format="raw",
            binary="binary",
        )

        with (
            patch("extractor.obtain._fetch_bytes", return_value=artifact),
            patch("extractor.obtain._fetch_text", return_value=digest),
        ):
            # obtain itself succeeds; the empty catalog check is in refresh.py
            result = obtain(instr, "1.0", tmp_path)
        assert result.exists()
