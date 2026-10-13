---
description: "Task list for schema extraction on contribution"
---

# Tasks: Schema Extraction on Contribution

**Input**: Design documents from `/specs/002-schema-extract-ci/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included because plan.md requires pytest coverage of token fill, checksum match and mismatch, unpack, change detection, and all-or-nothing publish in `tests/test_obtain.py` and `tests/test_refresh.py`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Extractor package at `extractor/`, registrations at `clis/`, catalogs at `schemas/`, workflow at `.github/workflows/extract-schemas.yml`
- Paths follow plan.md

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the refresh modules the plan names without touching the MCP server

- [X] T001 [P] Create `extractor/obtain.py` for download, checksum, and unpack
- [X] T002 [P] Create `extractor/refresh.py` so `python -m extractor.refresh --base <revision> --head <revision>` is the entry point described in `specs/002-schema-extract-ci/contracts/check-result.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Registration parsing, version fill, checksum, and unpack that every story uses

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 [P] Parse the `obtain` object in `extractor/cli_config.py`. Required fields are `artifact_url`, `checksum_url`, `format` (`raw`, `tar.gz`, or `zip`), and `binary`. `version_url` and `version_match` are optional and required together (`dependentRequired`). A registration with no `obtain` block fails the check. There is no fetch table keyed by CLI name
- [X] T004 Fill `{version}` and `{resolved}` in `extractor/obtain.py`. When `version_url` is omitted, `{resolved}` equals `{version}`. When `version_url` is set, fill `{version}` into `version_match` first; `version_match` must contain one capture group and that group is `{resolved}`. Fail before download if `artifact_url` and `checksum_url` contain neither `{version}` nor `{resolved}`
- [X] T005 Verify SHA-256 in `extractor/obtain.py` before unpack or execution. Accept a body that is 64 hex digits, or a `sha256sum` listing, using the line whose filename is the artifact URL’s basename. A missing checksum, a mismatch, or an unreadable body fails that version and does not run the program
- [X] T006 Unpack `raw`, `tar.gz`, and `zip` in `extractor/obtain.py`. `binary` is the installed filename for `raw`, or the archive member path otherwise. Unwrap at most three layers when a member is itself gzip or tar, then require the named binary

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Registration updates the catalog (Priority: P1) 🎯 MVP

**Goal**: A new or edited registration refreshes every declared version into `schemas/<tool>/<declared-version>.json`, and a branch this job can update receives that catalog commit

**Independent Test**: Add a registration for a CLI this project has never fetched, with one obtain instruction and two declared versions. Accept the change only after both versions have a catalog. Confirm no project code change was required and the maintainer did not produce those catalogs by hand.

### Tests for User Story 1

- [X] T007 [P] [US1] Add failing tests in `tests/test_obtain.py` for token fill, a matching checksum, a mismatched checksum that does not unpack, a missing version token, and a catalog with no commands
- [X] T008 [P] [US1] Add failing tests in `tests/test_refresh.py` that a two-version registration publishes both catalogs only after both succeed, and that catalogs for registrations outside the change set stay byte-identical

### Implementation for User Story 1

- [X] T009 [US1] Implement change detection and temporary-directory publish in `extractor/refresh.py`. Treat a registration as changed when its file is added or modified relative to the base. Refresh every version that file still declares. Copy into `schemas/<tool>/<declared-version>.json` only after every selected version succeeds. The catalog `version` equals the declared version and `subcommands` is non-empty. Exit 0 and print `published`, or `catalogs already match` when nothing changed. On failure print `FAIL <tool> <declared-version> <reason>` and leave `schemas/` unchanged
- [X] T010 [P] [US1] Add one `obtain` block to `clis/oc.yaml`: `artifact_url` `https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-{version}/openshift-client-linux.tar.gz`, `checksum_url` `https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-{version}/sha256sum.txt`, `format` `tar.gz`, `binary` `oc`
- [X] T011 [P] [US1] Add one `obtain` block to `clis/kubectl.yaml`: `version_url` `https://dl.k8s.io/release/stable-{version}.txt`, `version_match` with one capture group for the patch tag, `artifact_url` and `checksum_url` under `https://dl.k8s.io/release/{resolved}/bin/linux/amd64/`, `format` `raw`, `binary` `kubectl`
- [X] T012 [P] [US1] Add one `obtain` block to `clis/kustomize.yaml`: `version_url` for the GitHub releases list, `version_match` with one capture group for `kustomize/v{version}.<patch>`, `artifact_url` for `kustomize_v{resolved}_linux_amd64.tar.gz`, a `checksum_url` that receives the same `{resolved}` token, `format` `tar.gz`, `binary` `kustomize`
- [X] T013 [P] [US1] Add one `obtain` block to `clis/podman.yaml`: `version_url` for the GitHub releases list, `version_match` with one capture group for `v{version}.<patch>`, `artifact_url` for `podman-remote-static-linux_amd64.tar.gz`, a `checksum_url` that receives the same `{resolved}` token, `format` `tar.gz`, and `binary` set to the archive member path of the static binary
- [X] T014 [US1] Change `.github/workflows/extract-schemas.yml` to run `python -m extractor.refresh`, set `timeout-minutes: 90`, and on a same-repository push commit only `schemas/` when the refresh exits 0 and catalogs changed

**Checkpoint**: User Story 1 is independently testable. A registration-only change produces catalogs without a hand extraction step.

---

## Phase 4: User Story 2 - Incomplete catalogs are rejected (Priority: P2)

**Goal**: A contributor who cannot update the branch sees the differing catalog paths and the change is rejected

**Independent Test**: Propose a registration change that does not include the refreshed catalog and cannot be updated by the contributor. Confirm the change is rejected and the result names the catalog difference.

### Tests for User Story 2

- [X] T015 [P] [US2] Add failing tests in `tests/test_refresh.py` for exit 2 listing differing paths and for exit 0 with `catalogs already match` when the fresh catalogs are identical

### Implementation for User Story 2

- [X] T016 [US2] Implement the no-push outcome in `extractor/refresh.py`: exit 2, print each differing path under `catalogs differ:`, then `not updated`, and do not modify `schemas/`
- [X] T017 [US2] In `.github/workflows/extract-schemas.yml`, use that no-push outcome for a fork pull request and do not commit or push

**Checkpoint**: User Stories 1 and 2 both work. Same-repo branches get a catalog commit; fork pull requests get a difference list and a failure.

---

## Phase 5: User Story 3 - Removal stays in sync (Priority: P3)

**Goal**: Dropping a declared version or a registration removes the corresponding catalogs in the same publish step

**Independent Test**: Remove one declared version from a registration and confirm that version's catalog is gone after the change is accepted. Remove an entire registration and confirm none of its versions remain.

### Tests for User Story 3

- [X] T018 [P] [US3] Add failing tests in `tests/test_refresh.py` for removing one declared version and for deleting a registration file

### Implementation for User Story 3

- [X] T019 [US3] Delete retired catalogs in `extractor/refresh.py` only after every remaining selected version succeeds. Versions present in the base file and absent now are removed. Deleting the registration deletes `schemas/<tool>/`

**Checkpoint**: All three stories work. Adds, edits, rejections, and removals keep the catalog aligned with the registrations.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Remove the old per-CLI downloader from the check path and validate the quickstart

- [X] T020 Stop `.github/workflows/extract-schemas.yml` and the refresh path from calling `fetch_oc`, `fetch_kubectl`, `fetch_kustomize`, or `fetch_podman` in `scripts/extract-all-schemas.sh`
- [X] T021 [P] Document the one `obtain` block and its required fields in `CONTRIBUTING.md`
- [X] T022 Run the validation scenarios in `specs/002-schema-extract-ci/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Uses the refresh entry point from US1 but is testable with a no-push flag
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Uses the same publish step as US1 and is testable by deleting a version or a registration

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Obtain and config parsing finish in the foundational phase before story work
- Story complete before moving to the next priority

### Parallel Opportunities

- T001 and T002 can run in parallel
- T003 can run in parallel with T004 once `extractor/obtain.py` exists; T005 and T006 stay sequential in that file
- T007 and T008 can run in parallel
- T010, T011, T012, and T013 can run in parallel
- T015 can run in parallel with other untouched files once US1’s refresh entry point exists
- T018 can run in parallel with other untouched files once the publish step exists
- T021 can run in parallel with T020

---

## Parallel Example: User Story 1

```bash
# Tests together:
Task: "Add failing tests in tests/test_obtain.py"
Task: "Add failing tests in tests/test_refresh.py for two-version publish"

# Registration files together, after T003:
Task: "Add obtain block to clis/oc.yaml"
Task: "Add obtain block to clis/kubectl.yaml"
Task: "Add obtain block to clis/kustomize.yaml"
Task: "Add obtain block to clis/podman.yaml"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: A registration with one obtain instruction and two versions produces both catalogs without a code change
5. Demo the catalog commit on a same-repository branch

### Incremental Delivery

1. Complete Setup + Foundational → obtain and checksum work for any registration
2. Add User Story 1 → catalogs publish on success → MVP
3. Add User Story 2 → fork pull requests fail with a path list
4. Add User Story 3 → removed versions and registrations disappear from `schemas/`
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 refresh and workflow commit
   - Developer B: User Story 1 registration `obtain` blocks (`clis/oc.yaml`, `clis/kubectl.yaml`, `clis/kustomize.yaml`, `clis/podman.yaml`)
   - Developer C: User Story 2 no-push outcome, after the refresh entry point exists
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
