# Implementation Plan: Schema Extraction on Contribution

**Branch**: `002-schema-extract-ci` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-schema-extract-ci/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

When a CLI registration changes, refresh every declared version’s flag catalog before that change is accepted. The registration carries one obtain instruction (artifact URL, checksum URL, archive format, member name, and an optional version pointer). The check fills the declared version into that instruction, verifies SHA-256, then runs the existing extractor. It does not call the per-CLI download functions. Results land in `schemas/` only after every selected version succeeds. A branch this job can update receives a catalog commit. A fork pull request gets a difference list and a failure instead.

## Technical Context

**Language/Version**: Python 3.12 (CI and the existing `extractor` package)

**Primary Dependencies**: Existing extractor adapters (`cobra`, `help-parser`, `custom`), PyYAML, the standard library for HTTP, hashing, and archives. No new service framework.

**Storage**: Registration files in `clis/`. Generated catalogs in `schemas/<tool>/<declared-version>.json`. Downloaded programs exist only in the job’s temporary directory.

**Testing**: pytest. Unit tests for token fill, checksum match and mismatch, unpack, change detection, and the all-or-nothing publish. The server coverage gate stays on `cli_schema_mcp`.

**Target Platform**: GitHub-hosted Linux runner for the check. The same command runs locally.

**Project Type**: Repository check plus the existing extractor package. The MCP server is not modified.

**Performance Goals**: One changed registration finishes inside a 90-minute job. Untouched catalogs are not downloaded or rewritten.

**Constraints**: Checksum before execution. No per-CLI Python. No publish of a partial change. Server remains binary-free. OCI publishing, signing, and a catalog changelog are out of scope.

**Scale/Scope**: The change set is the registration files that differ from the base revision. Today that set is four CLIs (oc, kubectl, kustomize, podman) when their files change; a new CLI adds only a registration.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Pre-research | Result |
|------|----------------|--------|
| I. Schema accuracy | Catalogs stay extractor output. A checksum mismatch never runs the program. An empty command list fails the version. | Pass |
| II. Binary-free at runtime | Obtain and extract run in the refresh job only. The server does not import `extractor`. | Pass |
| III. Config-driven extensibility | A new CLI is a registration, not a new fetch function. The constitution’s list of per-CLI fields (adapter, versions, version-parse) is narrower than the clarified spec, which adds one obtain instruction. Justified below. | Pass with justification |
| IV. Typed MCP responses | This feature does not add or change an MCP tool. Catalog JSON keeps the existing flag fields. | Pass |
| V. Model-agnostic grounding | No model-specific logic. | Pass |
| Schemas committed, never hand-edited | The job writes generated JSON only, and only after a full success. | Pass |
| 80% server coverage | Unchanged. New tests cover the extractor refresh path; they are not a reason to lower the server gate. | Pass |
| Air-gapped OCI distribution | Out of scope. Phase 3 / spec 003. | Pass |

## Project Structure

### Documentation (this feature)

```text
specs/002-schema-extract-ci/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── registration.schema.json
│   └── check-result.md
└── tasks.md             # /speckit-tasks, not this command
```

### Source Code (repository root)

```text
extractor/
├── cli_config.py        # parse the obtain block
├── obtain.py            # substitute, download, checksum, unpack
├── refresh.py           # change set, temp dir, publish, exit codes
└── main.py              # existing single-version extract, called after obtain

.github/workflows/extract-schemas.yml
clis/*.yaml              # obtain block on each current registration
scripts/extract-all-schemas.sh   # stop being the CI downloader
tests/test_obtain.py
tests/test_refresh.py
schemas/<tool>/<version>.json
```

**Structure Decision**: Extend the existing `extractor` package and the existing workflow file. Do not add a second downloader in shell, and do not import this package from `cli_schema_mcp`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Constitution III lists only adapter, versions, and version-parse as per-CLI decisions. This feature adds one `obtain` block (artifact URL, checksum URL, format, member, optional version pointer). | The clarified spec requires a never-before-fetched CLI to refresh from its registration alone, with a checksum, and forbids a built-in fetch fallback. | Hardcoded `fetch_oc` / `fetch_kubectl` / `fetch_kustomize` / `fetch_podman` cannot accept a new CLI without a Python or shell edit, which fails FR-009. |

## Post-design Constitution Check

Re-checked against [research.md](research.md), [data-model.md](data-model.md), and [contracts/](contracts/).

| Gate | Post-design | Result |
|------|-------------|--------|
| I. Schema accuracy | SHA-256 is verified before unpack or extract. Empty catalogs fail. Identity stays the declared version, not the resolved patch tag. | Pass |
| II. Binary-free at runtime | Programs live in the job temp directory and are discarded. No server import of `extractor`. | Pass |
| III. Config-driven extensibility | New CLIs add YAML only. Shared unpack and checksum code is not per-CLI. The field-list gap remains the justified row above. | Pass with justification |
| IV. Typed MCP responses | No MCP change. | Pass |
| V. Model-agnostic grounding | No model logic. | Pass |
| Partial publish | Temporary directory; `schemas/` updates only after every selected version succeeds. | Pass |
| Fork versus same-repo | Exit 2 and a path list when the job must not push. Catalog commit only when it can update the branch. | Pass |

No unresolved clarifications. The 90-minute job limit is the planning default for the performance item deferred during clarification.
