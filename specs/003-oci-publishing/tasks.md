---
description: "Task list for OCI artifact publishing"
---

# Tasks: OCI Artifact Publishing

**Input**: Design documents from `/specs/003-oci-publishing/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: None — validation is end-to-end manual (push tag, pull artifact, run server). No new pytest tests required; this feature is a workflow + docs change.

**Organization**: Tasks are grouped by user story. US1 (pull path) and US2 (publish path) share the same artifact; they are validated together with the first tagged release. US3 (documentation) is independent.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Workflow: `.github/workflows/publish-schemas-oci.yml`
- Containerfile: `Containerfile` (repository root)
- README: `README.md` (repository root)
- Spec artifacts: `specs/003-oci-publishing/`

---

## Phase 1: Setup (Prerequisites)

**Purpose**: One-time configuration steps that must be in place before any publish attempt

- [ ] T001 Set `QUAY_USERNAME` and `QUAY_PASSWORD` as GitHub Actions repository secrets at `https://github.com/tosin2013/cli-schema-mcp/settings/secrets/actions` — use a quay.io robot account scoped to push-only on `takinosh/cli-schema-mcp`
- [ ] T002 Confirm `quay.io/takinosh/cli-schema-mcp` repository exists and is set to **public** visibility in quay.io repository settings (public visibility is required so consumers can pull without credentials)

---

## Phase 2: Foundational (Workflow Verification)

**Purpose**: Confirm the existing workflow file is correct before triggering a real publish

**⚠️ CRITICAL**: Workflow must be verified before pushing a version tag; a bad publish cannot be undone for a given tag

- [ ] T003 Review `.github/workflows/publish-schemas-oci.yml` and confirm: trigger is `push: tags: "v*"`, login uses `secrets.QUAY_USERNAME` and `secrets.QUAY_PASSWORD`, pushes `quay.io/takinosh/cli-schema-mcp:${tag}` first, then `quay.io/takinosh/cli-schema-mcp:latest` second, and both oras push commands use media type `application/vnd.cli-schema-mcp.schemas.v1.tar+gzip`

**Checkpoint**: Workflow is confirmed correct — ready to trigger US1/US2 validation

---

## Phase 3: User Stories 1 & 2 — Publish and Pull (Priority: P1) 🎯 MVP

**Goal (US2)**: A `v*` tag push triggers the workflow and publishes the artifact to quay.io automatically. **Goal (US1)**: An operator can pull the artifact on any machine that can reach quay.io, extract it, and run the MCP server with no internet access to GitHub.

**Independent Test**: Push `git tag v0.1.0 && git push origin v0.1.0`. Without further action, both `quay.io/takinosh/cli-schema-mcp:v0.1.0` and `:latest` exist and are pullable. Pulling and extracting produces a `schemas/` directory with at least five CLI subdirectories. Starting the MCP server with `SCHEMA_REGISTRY_PATH` pointing at the extracted path returns correct flag data for `oc 4.22`.

### Implementation for User Stories 1 & 2

- [ ] T004 [US2] Push the first release tag to trigger the publish workflow: `git tag v0.1.0 && git push origin v0.1.0` — watch the `Publish schemas OCI` Actions run at `https://github.com/tosin2013/cli-schema-mcp/actions` and confirm both steps pass
- [ ] T005 [US1] [US2] Verify the versioned artifact exists at `quay.io/takinosh/cli-schema-mcp:v0.1.0` by running `oras manifest fetch quay.io/takinosh/cli-schema-mcp:v0.1.0` and confirming a valid OCI manifest is returned
- [ ] T006 [US1] [US2] Verify `:latest` points to `v0.1.0` by running `oras manifest fetch quay.io/takinosh/cli-schema-mcp:latest` and confirming the digest matches the `v0.1.0` manifest digest
- [ ] T007 [US1] Pull and extract the artifact on a clean machine: `mkdir /tmp/pull && oras pull quay.io/takinosh/cli-schema-mcp:v0.1.0 --output /tmp/pull && mkdir /tmp/schemas && tar -xzf /tmp/pull/schemas.tar.gz -C /tmp/schemas` — confirm `ls /tmp/schemas/` shows at minimum: `oc  kubectl  kustomize  podman  tkn`
- [ ] T008 [US1] Start the MCP server against the extracted registry: `SCHEMA_REGISTRY_PATH=/tmp/schemas cli-schema-mcp` — run `curl http://localhost:5001/health` and confirm the server responds; optionally call `get_flags` for `oc 4.22` and confirm correct flag data is returned

**Checkpoint**: User Stories 1 and 2 are verified. Air-gapped pull path works; automated publish is confirmed.

---

## Phase 4: User Story 3 — Operator Documentation (Priority: P2)

**Goal**: A first-time operator can follow only the README OCI pull section and the Containerfile to configure the MCP server in an air-gapped deployment in under 10 minutes.

**Independent Test**: Give only the README and Containerfile to a fresh operator. They should be able to pull `quay.io/takinosh/cli-schema-mcp:latest`, extract the artifact, set `SCHEMA_REGISTRY_PATH`, and pass the health check without consulting source code.

### Implementation for User Story 3

- [ ] T009 [P] [US3] Add an "Air-gapped deployment (OCI)" section to `README.md` after the Configuration table. The section must include: the `oras pull quay.io/takinosh/cli-schema-mcp:latest --output /tmp/pull` command, the `tar -xzf` extraction command, the `SCHEMA_REGISTRY_PATH` env var explanation, and a complete example starting the server against the pulled registry
- [ ] T010 [P] [US3] Update `Containerfile` to add a comment block and an alternative OCI build stage showing: `oras pull quay.io/takinosh/cli-schema-mcp:latest` at build time, `tar -xzf` to extract schemas to `/schemas`, `ENV SCHEMA_REGISTRY_PATH=/schemas`, and removal of the `COPY schemas /app/schemas` line from the air-gapped variant. Add a comment explaining when to use each approach (default COPY vs. OCI pull)

**Checkpoint**: All three user stories are complete. The registry publishes automatically; consumers can pull and run without internet access; operators have clear instructions.

---

## Phase 5: Polish & Validation

**Purpose**: End-to-end validation per quickstart.md and consistency check

- [ ] T011 Run the complete validation sequence from `specs/003-oci-publishing/quickstart.md` — steps 1 through 6 — and confirm each expected output matches
- [ ] T012 [P] Run `pre-commit run --all-files` after all file changes and commit any auto-fixes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No code dependencies — can be done immediately; BLOCKS publish
- **Foundational (Phase 2)**: Depends on Phase 1 secrets being set; BLOCKS US1/US2 validation
- **US1/US2 (Phase 3)**: Depends on Phase 2 — requires first tag push; BLOCKS US3 validation via real artifact
- **US3 (Phase 4)**: Can be WRITTEN (T009, T010) in parallel with Phase 3; requires Phase 3 artifact to be available for the independent test
- **Polish (Phase 5)**: Depends on all phases complete

### User Story Dependencies

- **US1 + US2 (P1)**: Tightly coupled — same artifact. Both validated in Phase 3 by a single tag push.
- **US3 (P2)**: Writing T009 and T010 is independent; end-to-end test of US3 requires the Phase 3 artifact.

### Parallel Opportunities

- T009 (README update) and T010 (Containerfile update) can be written in parallel — different files
- T001 and T002 (setup) can be done in parallel

---

## Parallel Example: Phase 4 (US3)

```bash
# T009 and T010 can be worked simultaneously (different files):
Task: "Add OCI pull section to README.md"
Task: "Add oras pull layer to Containerfile"
```

---

## Implementation Strategy

### MVP First (US1 + US2 — one tagged release)

1. Complete Phase 1: Set secrets, confirm quay.io repo is public
2. Complete Phase 2: Review workflow file
3. Complete Phase 3: Push `v0.1.0`, verify artifact, pull and run server
4. **STOP and VALIDATE**: Air-gapped pull path is proven

### Full Delivery

1. MVP (above) → artifact is live
2. Add US3 (T009, T010): Write README section and Containerfile example
3. Polish (T011, T012): Validate quickstart, pre-commit clean

---

## Notes

- [P] tasks = different files, no dependencies
- T001 and T002 are manual configuration steps in external systems (GitHub, quay.io)
- The publish workflow (`.github/workflows/publish-schemas-oci.yml`) is already implemented and verified; the implementation tasks here are validation of the live system
- Once `v0.1.0` is tagged, versioned artifacts are immutable — choose the tag name carefully
- If the first publish fails, investigate the Actions log before re-tagging
