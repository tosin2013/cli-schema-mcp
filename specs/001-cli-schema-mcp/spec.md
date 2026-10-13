# Feature Specification: cli-schema-mcp

**Feature Branch**: `001-cli-schema-mcp`

**Created**: 2026-10-12

**Status**: Implemented

**Input**: PRD — cli-schema-mcp v1.0, Principal Solution Architect, Red Hat, 2026-10-07

## User Scenarios & Testing

### User Story 1 — Flag-accurate CLI suggestion (Priority: P1)

As a developer using Claude Code or another AI IDE with a CLI binary installed locally, I want the
AI tool to query a schema server before generating CLI commands, so that every flag it suggests
actually exists in my installed version of the tool.

**Why this priority**: This is the core value proposition. Without accurate flag suggestions the
entire project has no reason to exist. Every other story depends on the schema being queryable.

**Independent Test**: Call `get_flags("oc", "4.22", "rollout restart")` with the extracted oc 4.22
schema. Verify the response includes `--selector`, `--filename`, and `--namespace`, and does NOT
include `--force` (which was hallucinated in production by multiple AI tools).

**Acceptance Scenarios**:

1. **Given** the schema registry contains `schemas/oc/4.22.json`, **When** an agent calls
   `get_flags("oc", "4.22", "rollout restart")`, **Then** the response lists exactly the flags
   present in the 4.22 schema for that subcommand path, with name, type, shorthand, and default.

2. **Given** the schema registry has no entry for a requested version, **When** an agent calls
   `get_flags("oc", "4.23", "rollout restart")`, **Then** the response returns the nearest
   available version's flags with a `matched_version` note field (not an error).

3. **Given** an invalid subcommand path is requested, **When** an agent calls
   `get_flags("oc", "4.22", "rollout nonexistent")`, **Then** the response is
   `{"status": "error", "error": "subcommand not found", ...}`.

4. **Given** the schema registry contains `schemas/oc/4.22.json`, **When** an agent calls
   `list_subcommands("oc", "4.22", "rollout")`, **Then** the response lists all valid subcommands
   under `rollout` (e.g. history, latest, pause, restart, resume, status, undo).

---

### User Story 2 — Command validation before autonomous execution (Priority: P2)

As an AI agent orchestrating CLI calls autonomously (Event-Driven Ansible, OpenShift Lightspeed
cluster-interaction, CI/CD pipeline), I want to validate a fully-formed command string before
executing it, so that bad flags are caught structurally before any system is affected.

**Why this priority**: Autonomous execution is the highest-stakes use case. A wrong flag at this
layer runs without human review.

**Independent Test**: Call `validate_command("oc", "4.22", "oc rollout restart deployment/myapp --force")`
and verify `{"valid": false, "errors": ["--force is not a valid flag for 'oc rollout restart' in version 4.22"]}`.

**Acceptance Scenarios**:

1. **Given** a valid command string, **When** `validate_command` is called, **Then**
   `{"status": "success", "valid": true, "errors": []}` is returned.

2. **Given** a command with one hallucinated flag, **When** `validate_command` is called, **Then**
   `valid` is `false` and `errors` names the specific invalid flag and its subcommand context.

3. **Given** a command with multiple invalid flags, **When** `validate_command` is called, **Then**
   all invalid flags are listed in `errors` (not just the first one).

4. **Given** the `detect_version` tool is available and the binary is present, **When**
   `detect_version("oc")` is called, **Then** the response includes the detected version string and
   the matched schema version (e.g. `"4.22.1"` → `matched_schema: "4.22"`).

5. **Given** the binary is absent, **When** `detect_version("oc")` is called, **Then**
   `{"status": "error", "error": "binary not found", ...}` is returned (no crash, no exception).

---

### User Story 3 — CLI maintainer adds new tool via YAML config (Priority: P3)

As a maintainer of `tkn` (Tekton CLI) or any other community CLI, I want to add my tool to the
schema registry by submitting only a YAML config file, with no Python code changes required, so
that the barrier to community contribution is as low as possible.

**Why this priority**: Extensibility is a first-class requirement. If adding a CLI requires code
changes, the registry cannot scale to the broader community.

**Independent Test**: Create `clis/tkn.yaml` with `adapter: cobra` and versions `["0.38"]`. Run
`python -m extractor tkn 0.38`. Verify `schemas/tkn/0.38.json` is produced, is valid JSON, and
contains flag entries for at least the `tkn pipeline` subcommand.

**Acceptance Scenarios**:

1. **Given** a `clis/<name>.yaml` with `adapter: cobra` is added, **When** the extractor is run,
   **Then** `schemas/<name>/<version>.json` is produced with no code changes to the server or
   extractor.

2. **Given** a `clis/<name>.yaml` with `adapter: help-parser` and regex patterns is added,
   **When** the extractor is run against a CLI that does not implement Cobra `__complete`,
   **Then** a valid schema JSON is produced with flag names, types, and shorthands.

3. **Given** `list_supported()` is called after new schemas are added, **Then** the new CLI and
   its versions appear in the response.

---

### Edge Cases

- What happens when `detect_version` is called and the binary is absent? → structured error, not crash
- What happens when schema for the requested version is not in registry? → nearest match + `matched_version` note
- What happens when a CLI requires authentication to run `--help` subcommands? → out of scope for Phase 1; documented assumption
- How does the system handle version strings that don't parse to semver (e.g. `tkn 0.37.0-rc1`)? → best-effort match, fallback to latest
- What happens when `validate_command` receives a malformed command string? → parse error returned, not a crash
- What happens when `get_flags` is called for a subcommand path that doesn't exist? → `{"status": "error", "error": "subcommand not found"}`

## Requirements

### Functional Requirements

**MCP Tools**

- **FR-001**: `get_flags(tool, version, command)` MUST return all valid flags for the given
  command path and version as a structured list. Each flag MUST include: `name` (--long-form),
  `type` (string | bool | int | duration | stringArray), `shorthand` (-x, if any), `default`
  (string, if set), `description` (string), `deprecated` (bool).

- **FR-002**: `list_subcommands(tool, version, parent?)` MUST return the list of valid subcommand
  names under `parent`, or top-level command names if `parent` is omitted.

- **FR-003**: `validate_command(tool, version, command_string)` MUST parse the command string and
  return `{"valid": bool, "errors": [str]}` where each error identifies the invalid flag by name
  and its subcommand context.

- **FR-004**: `detect_version(tool)` MUST execute the binary's version command in the local
  environment, parse the output using the pattern from `clis/<tool>.yaml`, and return
  `{"version": str, "matched_schema": str}`. MUST return `{"status": "error", ...}` if the binary
  is absent or the version command fails.

- **FR-005**: `list_supported()` MUST return a dict mapping each tool name to the list of schema
  versions available in the registry.

**Schema Extraction (build-time)**

- **FR-006**: The Cobra adapter MUST extract schemas using the CLI binary's built-in completion
  or help tree mechanisms for structured, reliable output.

- **FR-007**: The help-parser adapter MUST extract schemas by parsing `--help` output with
  configurable regex patterns declared in the CLI's YAML config, for non-Cobra CLIs.

- **FR-008**: A custom adapter hook MUST be supported for CLIs with unusual help formats,
  accepting a user-supplied extraction script path in the YAML config.

**CLI Plugin Model**

- **FR-009**: A new CLI MUST be addable via a `clis/<name>.yaml` file with these fields:
  `name`, `display_name`, `binary`, `adapter` (cobra | help-parser | custom), `versions[]`,
  `version_command`, `version_parse` (regex pattern), `upstream_repo`, `maintainers[]`.

- **FR-010**: CI MUST automatically run the extractor against all declared versions when a
  `clis/*.yaml` file is added or modified in a PR.

**Version Resolution**

- **FR-011**: Version resolution MUST use this precedence: exact string match → major.minor
  match (4.22.1 → 4.22) → latest available → for OCP specifically, prefer EUS (even minor)
  versions when resolving ambiguous requests.

**Schema Registry**

- **FR-012**: All extracted schemas MUST be stored as `schemas/<tool>/<version>.json` and
  committed to the repository.

- **FR-013**: Schemas MUST be publishable as OCI artifacts to support air-gapped deployments.

**Server Standards (from template)**

- **FR-014**: All tool functions MUST return `Dict[str, Any]` with a `status` field
  (`"success"` or `"error"`).

- **FR-015**: All tool functions MUST catch all exceptions and return a structured error dict;
  they MUST NOT raise.

### Key Entities

- **CLI Tool**: name, display_name, binary, adapter type, versions[], version_command,
  version_parse regex pattern, upstream_repo, maintainers[]

- **Schema**: tool + version identifier → root command node with recursive subcommand tree;
  stored as `schemas/<tool>/<version>.json`

- **Subcommand**: name (string), description (string), flags (Flag[]), children (Subcommand[])

- **Flag**: name (--long), shorthand (-x | null), type (string | bool | int | duration |
  stringArray), default (string | null), description (string), deprecated (bool)

- **Version**: semver string; resolution maps it to the nearest schema file in the registry

## Success Criteria

### Measurable Outcomes

- **SC-001**: `validate_command` rejects 100% of known hallucinated-flag test cases for supported
  tools and versions; effective CLI flag hallucination rate for supported tools is ~0%.

- **SC-002**: ≥ 4 CLIs supported at Phase 1 completion: `oc`, `kubectl`, `kustomize`, `podman`.
  All four implement Cobra `__complete` and use the cobra adapter. The help-parser adapter
  remains for CLIs that do not.

- **SC-003**: All OCP 4.18–4.22 (`oc`) and Kubernetes 1.31–1.35 (`kubectl`) version schemas
  present in the registry at initial release.

- **SC-004**: Time to add a new Cobra CLI to the registry is < 30 minutes (YAML config only;
  no Python code changes).

- **SC-005**: 80% test coverage maintained across all tool modules, enforced in CI.

## Assumptions

- Auth is disabled by default (`ENABLE_AUTH=False` in `.env.example` and as the `settings.py`
  code default) — schema data is not sensitive and does not require bearer token protection
  for Phase 1.
- Mobile and GUI interactions are out of scope — CLI only.
- Schema extraction requires the CLI binary to be available at build time (CI). It is NOT
  required at server runtime.
- CLIs that require authentication to display `--help` output are out of scope for Phase 1
  and will be documented as a known limitation.
- OCI artifact publishing is a Phase 3 deliverable. Phase 1 uses JSON files committed to the
  repository and served from the local filesystem.
- The server is deployed as a container and/or run locally; no SaaS or managed hosting is
  assumed for Phase 1.
- The MCP server itself does not bundle any schema extraction logic — extraction is a
  separate package (`extractor/`) run at build time only.
