# Feature Specification: Schema Extraction on Contribution

**Feature Branch**: `002-schema-extract-ci`

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "When a CLI registration is added or changed, refresh the versioned flag catalog for every declared version before that change is accepted. The maintainer does not extract the catalog by hand. This is roadmap entry 002 — Schema Extraction CI Pipeline. Out of scope: packaged catalog distribution, signing, and a catalog changelog."

## Clarifications

### Session 2026-10-12

- Q: When someone adds a CLI this project has never fetched before, should the registration alone be enough to refresh its flag catalog? → A: Yes. The registration includes how to obtain each declared version, and the check uses only that.
- Q: Does one obtain instruction cover every declared version of a CLI, or does each version need its own? → A: One instruction per CLI. Each declared version is filled into it.
- Q: Before the check runs a program it just obtained, what proof must that one instruction include? → A: The instruction also names a checksum. The check runs the program only when the checksum matches.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registration updates the catalog (Priority: P1)

As a maintainer adding a CLI to the registry, I want every version I declare to appear in the flag catalog as part of accepting my change, so that I do not run a separate extraction step and reviewers are not left with a registration that has no catalog.

**Why this priority**: A registration without a catalog does not help an agent. This is the outcome of the feature.

**Independent Test**: Add a registration for a CLI this project has never fetched, with one obtain instruction and two declared versions. Accept the change only after both versions have a catalog. Confirm no project code change was required and the maintainer did not produce those catalogs by hand.

**Acceptance Scenarios**:

1. **Given** a new CLI registration with one obtain instruction, a checksum, and one or more declared versions, **When** the checksum matches and the change is accepted, **Then** the catalog contains one entry per declared version and each entry lists that tool's commands and flags, with no project code change.
2. **Given** an existing registration whose declared version list changes, **When** the change is accepted, **Then** the catalog matches the new version list, including versions that were added.
3. **Given** a registration change made by someone who is allowed to update the project branch, **When** the catalogs are produced, **Then** those catalogs are saved with the change so the maintainer does not copy them in by hand.

---

### User Story 2 - Incomplete catalogs are rejected (Priority: P2)

As a reviewer, I want a registration change rejected when its catalog was not refreshed and the contributor cannot save that refresh back to the project, so that the registry cannot merge a registration that points at missing or stale flags.

**Why this priority**: Outside contributors often cannot update the project branch directly. Rejection is what keeps the catalog honest in that case.

**Independent Test**: Propose a registration change that does not include the refreshed catalog and cannot be updated by the contributor. Confirm the change is rejected and the result names the catalog difference.

**Acceptance Scenarios**:

1. **Given** a registration change whose catalog is missing or different, and the contributor cannot update the branch, **When** the check finishes, **Then** the change is not accepted and the result shows which catalog entries differ.
2. **Given** a registration change whose catalog already matches every declared version, **When** the check finishes, **Then** the change is allowed without a further catalog edit.

---

### User Story 3 - Removal stays in sync (Priority: P3)

As a maintainer retiring a version or a CLI, I want the catalog to drop what I removed, so that agents are not offered flags for a version the project no longer claims to support.

**Why this priority**: Stale catalog entries recreate the version-mismatch problem this registry exists to prevent. It matters after the add path works.

**Independent Test**: Remove one declared version from a registration and confirm that version's catalog is gone after the change is accepted. Remove an entire registration and confirm none of its versions remain.

**Acceptance Scenarios**:

1. **Given** a registration that drops one declared version, **When** the change is accepted, **Then** that version's catalog is removed and the versions still declared remain.
2. **Given** a registration that is removed entirely, **When** the change is accepted, **Then** no catalog remains for that CLI.

---

### Edge Cases

- What happens when a declared version's program cannot be obtained, or the registration has no obtain instruction? The check fails, names the tool and version, and does not publish a catalog for that version. The check does not fall back to a built-in fetch method.
- What happens when the obtain instruction has no place to fill in the version? The check fails for that registration and does not publish a catalog.
- What happens when the checksum is missing or does not match? The check does not run the program, fails, names the tool and version, and does not publish a catalog for that version.
- What happens when extraction produces a catalog with no commands? The check fails for that tool and version, and the change is not accepted.
- What happens when one version of a changed registration succeeds and another fails? The change is not accepted, and the failed version is named. A mixed update for that registration is not treated as complete.
- What happens when several registrations change together? Every changed registration is refreshed. Registrations that were not part of the change are left as they are.
- What happens when the refreshed catalog is identical to the one already stored? The check passes and no empty follow-up change is required.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When a CLI registration is added or its declared versions change, the project MUST refresh the flag catalog for every version that registration declares before the change can be accepted.
- **FR-002**: When the person making the change is allowed to update the project branch, the refreshed catalog MUST be saved with that change so the maintainer does not extract or copy it by hand.
- **FR-003**: When the contributor cannot update the project branch, a registration whose catalog is missing or different MUST be rejected, and the result MUST show which catalog entries differ.
- **FR-004**: Each refreshed catalog MUST identify the tool and the version and MUST list commands and their flags. A catalog with no commands MUST fail the check.
- **FR-005**: If a declared version's program cannot be obtained, the check MUST fail, MUST name that tool and version, and MUST NOT publish a catalog for that version.
- **FR-006**: The check MUST refresh only registrations that were added, modified, or removed. Catalogs for untouched registrations MUST stay unchanged.
- **FR-007**: Removing a declared version MUST remove that version's catalog. Removing a registration MUST remove the catalogs for that CLI.
- **FR-008**: A change MUST be accepted only when every declared version of every changed registration succeeded. A failure of one version MUST reject the whole change.
- **FR-009**: A registration MUST contain one obtain instruction for the CLI. The check MUST fill each declared version into that instruction and MUST use only the result. The instruction MUST include a version placeholder; an instruction without one MUST fail the check. A CLI the project has never fetched before MUST be refreshable from its registration alone, with no project code change. A registration that omits the instruction MUST fail the check.
- **FR-010**: That same instruction MUST name a checksum, with the declared version filled in the same way. The check MUST run the program only when the checksum matches. A missing or mismatched checksum MUST fail the check for that version without running the program and without publishing a catalog.

### Key Entities

- **CLI registration**: The maintainer-owned description of one CLI, including the versions the project claims to support and one obtain instruction. That instruction names the program and a checksum. Each declared version is filled into both. Adding a CLI does not require a code change. The check does not keep a separate fetch list.
- **Flag catalog**: The versioned list of commands and flags for one declared version of one CLI. Agents read this catalog instead of guessing flags.
- **Check result**: The pass or fail record for a registration change, including the tool and version when a refresh fails and the catalog difference when a contributor cannot save the refresh.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a registration-only change, the maintainer performs zero separate extraction steps. Every declared version is in the catalog before the change is accepted.
- **SC-002**: 100% of declared versions on a changed registration are present in the catalog, or the change is rejected. A partial version list is never accepted.
- **SC-003**: When a declared program cannot be obtained, the check result names that tool and version in the failure the maintainer reads.
- **SC-004**: After a change to one registration, catalogs for CLIs that were not part of the change remain identical to their previous contents.

## Assumptions

- Feature 001 has already produced the versioned flag catalog and the base registration. This feature adds one obtain instruction per CLI, with each declared version filled in, and refreshes that catalog. It does not redefine which flags are valid.
- Obtaining each declared CLI program is required while the catalog is refreshed, and the registration is the only source for how to do that. The program is run only after its checksum matches. The running schema service still does not need those programs.
- A contributor who can update the project branch gets the catalog saved for them. A contributor who cannot gets a rejection and a difference report instead of a direct update.
- A refresh may already have been drafted. This feature is complete only when a real registration change produces the catalog behavior above.
- Packaged distribution of the catalog, signing, and a human-readable catalog changelog are out of scope.
- Registrations that need a secret or an interactive login before they can show their commands stay out of scope, matching the Phase 1 limit from feature 001.
