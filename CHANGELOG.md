# Changelog

All notable changes to cli-schema-mcp are documented here.

Detailed release notes are available at [GitHub Releases](https://github.com/tosin2013/cli-schema-mcp/releases).

## [0.1.4] - 2026-10-15

### Added

- New MCP tool: `get_download_info(tool, version=None)` — returns artifact download URLs,
  checksum URLs, archive format, and binary path from `clis/*.yaml` registrations. Works
  entirely from the registration file with no binary or network required. Returns
  `system_package` guidance for CLIs without an obtain block (e.g. nmstate). Designed for
  containerized deployments where the agent needs to guide the user to install a CLI.
- `detect_version` now returns `status=binary_not_found` (instead of a bare error) when
  the CLI binary is not in PATH. Includes `install_hint` and a `suggestion` to call
  `get_download_info()`, so agents can surface actionable install guidance.

---

## [0.1.3] - 2026-10-15

### Fixed

- `validate_command` false-positive flag matches on hyphenated positional arguments
  (filenames, namespace names, pod names, resource identifiers) — fixes #16.
  `_parse_flags_from_string` now tokenizes on whitespace with `shlex.split` before
  classifying each token, instead of regex-scanning the raw string.
  The `--` POSIX end-of-flags separator is also now recognized correctly.

---

## [0.1.2] - 2026-10-14

### Added

- `virtctl` (KubeVirt) 1.8 and 1.9 schemas — 35 subcommands, 22 flags
- `nmstate` (`nmstatectl`) 2.2 schema — 14 subcommands including apply, show, edit, validate
- `skip_checksum: true` obtain field for CLIs without published checksum files (virtctl uses this)
- OCI artifact at `quay.io/takinosh/cli-schema-mcp:v0.1.2` / `:latest`

### Fixed

- help-parser adapter now recognises `SUBCOMMANDS:` section header (Rust/clap CLIs)
- help-parser subcommand detection no longer matches flags as subcommands
- Registrations without an `obtain` block are now silently skipped in CI (not FAILed)

---

## [0.1.1] - 2026-10-14

### Added

- OCI artifact publishing to `quay.io/takinosh/cli-schema-mcp` on every `v*` tag
- `schemas/tkn/0.45.json` and `schemas/tkn/0.46.json` — Tekton CLI flag catalogs
- `SCHEMA_REGISTRY_PATH` env var documented in README for air-gapped deployments
- Containerfile: commented OCI pull alternative for air-gapped image builds
- `clis/tkn.yaml` — Tekton CLI registration (first community CLI)

### Fixed

- cobra adapter: replaced per-branch `seen` set with globally shared set, preventing
  exponential node revisiting in CLIs with large help subcommand trees
- `extractor/refresh.py`: recursion limit raised to 5000 for large schema serialization
- `extractor/obtain.py`: `version_match` patterns now capture full semver (not just patch)
  for kustomize, podman, and kubectl; kubectl artifact URL now includes required `v` prefix
- `extractor/obtain.py`: GitHub API requests now include `GITHUB_TOKEN` Authorization header
  to avoid unauthenticated rate limiting in GitHub Actions
- `publish-schemas-oci.yml`: use relative path for `oras push` (absolute paths rejected)
- All pre-commit hooks pass: check-yaml exclusion for third-party fixtures,
  types-PyYAML added to mypy stubs, pydocstyle exclusions for tool metadata docstrings

## [0.1.0] - 2026-10-12

### Added

- Initial release of cli-schema-mcp — a vendor-neutral MCP server for version-pinned
  CLI flag schemas
- Five MCP tools: `get_flags`, `list_subcommands`, `validate_command`, `detect_version`,
  `list_supported`
- Schema registry for oc 4.18–4.22, kubectl 1.31–1.35, kustomize 5.3–5.5, podman 5.2–5.4
- Cobra, help-parser, and custom extractor adapters
- `extractor/obtain.py`: generic download, SHA-256 verify, unpack (raw/tar.gz/zip)
- `extractor/refresh.py`: change-set detection, all-or-nothing publish, exit 0/1/2,
  fork-PR `--no-push` path, version retirement
- `clis/*.yaml`: obtain blocks for all four initial CLIs
- `extract-schemas.yml`: schema extraction CI — auto-extracts on `clis/` changes,
  commits catalogs to branch, rejects fork PRs with catalog differences
- `publish-schemas-oci.yml`: OCI publishing workflow skeleton (targeting quay.io)
- OAuth 2.0 integration (off by default, `ENABLE_AUTH=False`)
- PostgreSQL token storage (required only when auth is enabled)
- Multiple transport protocols: HTTP, SSE, streamable-HTTP
- SSL/TLS support
- Structured JSON logging with structlog
- Pydantic-based configuration management
- Red Hat UBI9 container image
- OpenShift deployment manifests
- 355 tests, 84%+ coverage
- Pre-commit: ruff, mypy, pydocstyle, bandit
