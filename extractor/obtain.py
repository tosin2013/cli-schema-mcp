"""Download, verify, and unpack a CLI binary for schema extraction."""

from __future__ import annotations

import hashlib
import io
import re
import stat
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ObtainInstruction:
    artifact_url: str
    checksum_url: str
    format: str  # "raw", "tar.gz", or "zip"
    binary: str
    version_url: str | None = None
    version_match: str | None = None


class ObtainError(Exception):
    """Raised when any obtain step fails."""


def _fill_tokens(template: str, version: str, resolved: str) -> str:
    return template.replace("{version}", version).replace("{resolved}", resolved)


def _fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=120) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def _fetch_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=600) as resp:  # noqa: S310
        return resp.read()


def resolve_version(instr: ObtainInstruction, version: str) -> str:
    """Return the resolved patch tag, or version when version_url is absent."""
    if not instr.version_url:
        return version
    url = _fill_tokens(instr.version_url, version, version)
    body = _fetch_text(url)
    pattern = _fill_tokens(instr.version_match, version, version)  # type: ignore[arg-type]
    m = re.search(pattern, body)
    if not m or not m.groups():
        raise ObtainError(f"version_match {pattern!r} did not match body from {url}")
    return m.group(1)


def _verify_checksum(artifact_bytes: bytes, artifact_basename: str, checksum_body: str) -> None:
    """Verify SHA-256. Accepts a bare 64-hex digest or a sha256sum listing."""
    actual = hashlib.sha256(artifact_bytes).hexdigest()
    body = checksum_body.strip()
    if re.fullmatch(r"[0-9a-fA-F]{64}", body):
        expected = body.lower()
    else:
        # sha256sum listing: "<digest>  <filename>" or "<digest> *<filename>"
        expected = None
        for line in body.splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                digest, fname = parts
                fname = fname.lstrip("* ")
                if fname == artifact_basename and re.fullmatch(r"[0-9a-fA-F]{64}", digest):
                    expected = digest.lower()
                    break
        if expected is None:
            raise ObtainError(
                f"checksum file does not contain an entry for {artifact_basename!r}"
            )
    if actual != expected:
        raise ObtainError(
            f"SHA-256 mismatch for {artifact_basename}: expected {expected}, got {actual}"
        )


def _extract_from_tar(data: bytes, member_path: str, dest: Path) -> Path:
    """Extract member_path from a tar (possibly gzip-compressed), up to 3 layers."""
    for _layer in range(3):
        buf = io.BytesIO(data)
        try:
            with tarfile.open(fileobj=buf) as tf:
                try:
                    member = tf.getmember(member_path)
                except KeyError:
                    # member not at top level — check if it's still inside another archive
                    names = tf.getnames()
                    # look for a nested archive
                    nested = next(
                        (n for n in names if n.endswith((".tar.gz", ".tgz", ".tar"))),
                        None,
                    )
                    if nested is None:
                        raise ObtainError(
                            f"member {member_path!r} not found in archive; members: {names[:10]}"
                        ) from None
                    nested_f = tf.extractfile(tf.getmember(nested))
                    if nested_f is None:
                        raise ObtainError(f"could not read nested archive {nested!r}")
                    data = nested_f.read()
                    continue
                f = tf.extractfile(member)
                if f is None:
                    raise ObtainError(f"member {member_path!r} is not a regular file")
                binary_data = f.read()
                dest.write_bytes(binary_data)
                dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                return dest
        except tarfile.TarError as exc:
            raise ObtainError(f"tar extraction failed: {exc}") from exc
    raise ObtainError(f"exceeded 3 layers of nesting looking for {member_path!r}")


def _extract_from_zip(data: bytes, member_path: str, dest: Path) -> Path:
    buf = io.BytesIO(data)
    try:
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            if member_path not in names:
                raise ObtainError(
                    f"member {member_path!r} not found in zip; members: {names[:10]}"
                )
            dest.write_bytes(zf.read(member_path))
            dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            return dest
    except zipfile.BadZipFile as exc:
        raise ObtainError(f"zip extraction failed: {exc}") from exc


def obtain(
    instr: ObtainInstruction,
    version: str,
    dest_dir: Path,
) -> Path:
    """Download, verify, and unpack the binary for *version* into *dest_dir*.

    Returns the path to the installed binary.
    """
    resolved = resolve_version(instr, version)

    artifact_url = _fill_tokens(instr.artifact_url, version, resolved)
    checksum_url = _fill_tokens(instr.checksum_url, version, resolved)

    if "{version}" not in instr.artifact_url and "{resolved}" not in instr.artifact_url:
        raise ObtainError(
            f"artifact_url contains neither {{version}} nor {{resolved}}: {instr.artifact_url!r}"
        )

    artifact_bytes = _fetch_bytes(artifact_url)
    checksum_body = _fetch_text(checksum_url)

    import posixpath
    artifact_basename = posixpath.basename(artifact_url.split("?")[0])
    _verify_checksum(artifact_bytes, artifact_basename, checksum_body)

    dest_dir.mkdir(parents=True, exist_ok=True)

    if instr.format == "raw":
        dest = dest_dir / instr.binary
        dest.write_bytes(artifact_bytes)
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return dest
    elif instr.format == "tar.gz":
        dest = dest_dir / Path(instr.binary).name
        return _extract_from_tar(artifact_bytes, instr.binary, dest)
    elif instr.format == "zip":
        dest = dest_dir / Path(instr.binary).name
        return _extract_from_zip(artifact_bytes, instr.binary, dest)
    else:
        raise ObtainError(f"unsupported format: {instr.format!r}")
