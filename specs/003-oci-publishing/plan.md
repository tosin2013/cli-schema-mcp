# Implementation Plan: OCI Artifact Publishing

**Branch**: `003-oci-publishing` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-oci-publishing/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Package the `schemas/` directory as a single OCI artifact (`.tar.gz` layer, custom media type) and push it to `quay.io/takinosh/cli-schema-mcp` on every `v*` tag push — both as a versioned tag and as `:latest`. Consumers pull without credentials and point `SCHEMA_REGISTRY_PATH` at the extracted directory. The MCP server already supports this env var. The workflow file `publish-schemas-oci.yml` exists but targets GHCR; it needs to be retargeted to quay.io and the README + Containerfile need OCI pull documentation.

## Technical Context

**Language/Version**: YAML (GitHub Actions workflow); Bash (packaging steps); no new Python

**Primary Dependencies**: `oras` CLI via `oras-project/setup-oras@v2` (already in workflow); `tar` (standard Linux)

**Storage**: quay.io OCI registry — `quay.io/takinosh/cli-schema-mcp`

**Testing**: Manual end-to-end (pull + extract + server start); no new pytest tests needed. The publish workflow itself is the integration test.

**Target Platform**: GitHub-hosted Linux runner for publish; any Linux/macOS/OCP environment for pull

**Project Type**: GitHub Actions workflow update + documentation

**Performance Goals**: Artifact available within 5 minutes of tag push (per SC-001). The `schemas/` tar is small (< 10 MB total for current CLIs).

**Constraints**: Public pull (no credentials for consumers). Single registry. No signing. No multi-registry. Versioned tags are immutable once pushed.

**Scale/Scope**: One workflow file, one README section, one Containerfile update. SCHEMA_REGISTRY_PATH already in server settings — no Python changes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Pre-research | Result |
|------|-------------|--------|
| I. Schema accuracy | OCI artifact contains pre-extracted schema JSON — same files committed in the repo. No generation at publish time. | Pass |
| II. Binary-free at runtime | Server reads schemas from SCHEMA_REGISTRY_PATH (filesystem). No binary download at runtime. | Pass |
| III. Config-driven extensibility | OCI publish is automatic; new CLIs appear in the artifact when extraction CI (spec 002) adds their schemas. No code change per CLI. | Pass |
| IV. Typed MCP responses | No MCP tool changes. | Pass |
| V. Model-agnostic grounding | No model logic. | Pass |
| Air-gapped OCI distribution | This feature IS the air-gapped OCI distribution path. | Core deliverable |
| 80% server coverage | No Python code changes; coverage gate unaffected. | Pass |

No violations. No Complexity Tracking entries required.

## Post-design Constitution Check

| Gate | Post-design | Result |
|------|-------------|--------|
| I. Schema accuracy | JSON files are a verbatim snapshot of `schemas/` at the tagged commit — untouched by the publish process. | Pass |
| II. Binary-free at runtime | SCHEMA_REGISTRY_PATH points at extracted JSON files; server reads them as static data. | Pass |
| III. Config-driven extensibility | Artifact content is determined by what's in `schemas/` — driven by `clis/*.yaml` config via spec 002 pipeline. | Pass |

## Project Structure

### Documentation (this feature)

```text
specs/003-oci-publishing/
├── plan.md              ← this file
├── research.md          ← Phase 0 (decisions on format, registry, auth)
├── data-model.md        ← Phase 1 (artifact structure, SCHEMA_REGISTRY_PATH)
├── quickstart.md        ← Phase 1 (pull, extract, run, Containerfile test)
├── contracts/
│   └── publish-contract.md  ← Phase 1 (pull API, guarantees, required secrets)
└── tasks.md             ← Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
.github/workflows/publish-schemas-oci.yml   ← update registry target + add :latest push
Containerfile                                ← add oras pull layer + ENV SCHEMA_REGISTRY_PATH
README.md                                    ← add OCI pull section
```

**Structure Decision**: Minimal surface area — one workflow file, two documentation files. No new Python packages or source directories.
