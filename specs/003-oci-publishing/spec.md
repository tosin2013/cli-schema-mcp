# Feature Specification: OCI Artifact Publishing

**Feature Branch**: `003-oci-publishing`

**Created**: 2026-10-14

**Status**: Draft

**Input**: User description: "Package the schemas/ directory as an OCI artifact and push it to quay.io/takinosh/cli-schema-mcp on each tagged release, so air-gapped OCP clusters can pull the schema registry without internet access. Registry destination: quay.io/takinosh/cli-schema-mcp. Scope excludes schema signing, multi-registry push, and schema diffing/changelog. Workflow file publish-schemas-oci.yml already exists but targets GHCR; update it to quay.io. (Roadmap entry 003)"

## Clarifications

### Session 2026-10-14

- **Registry destination**: Decided — `quay.io/takinosh/cli-schema-mcp`
- **Tag strategy**: Versioned tag (`v*`) plus `:latest` on every tagged release
- **Auth**: `QUAY_USERNAME` and `QUAY_PASSWORD` repository secrets
- **Scope**: Single registry, no signing, no changelog — start simple and verify the OCI path works

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Air-gapped enterprise pulls schema registry (Priority: P1)

As an enterprise deployer running OCP in an isolated network, I want to pull the CLI flag schema registry as a single OCI artifact so that my air-gapped cluster can validate CLI commands without any internet connection at runtime.

**Why this priority**: This is the core value proposition. Without it, air-gapped deployments cannot use the MCP server at all. Everything else (signing, changelog) is secondary to proving the pull path works.

**Independent Test**: On a machine with no direct access to the schema registry GitHub repository, pull `quay.io/takinosh/cli-schema-mcp:latest`, extract the schemas archive, and confirm that `schemas/oc/4.22.json` exists and is a valid non-empty JSON file.

**Acceptance Scenarios**:

1. **Given** a versioned release tag is pushed to the repository, **When** the publish workflow completes, **Then** `quay.io/takinosh/cli-schema-mcp:<tag>` and `quay.io/takinosh/cli-schema-mcp:latest` both exist and are pullable.
2. **Given** a network-isolated environment that can reach quay.io, **When** the OCI artifact is pulled and extracted, **Then** the `schemas/` directory structure matches what is committed in the repository at that tag.
3. **Given** the OCI artifact has been pulled and extracted to a local path, **When** the MCP server is started with `SCHEMA_REGISTRY_PATH` pointing at that path, **Then** all five MCP tools return correct results for supported CLIs and versions.

---

### User Story 2 - Maintainer publishes a new schema release (Priority: P1)

As a maintainer, I want publishing to happen automatically when I push a version tag, so that I do not manually package or upload anything.

**Why this priority**: Manual publishing is error-prone and defeats the purpose of CI/CD. Tied in priority with P1 because the pull path depends on the publish path.

**Independent Test**: Push tag `v0.1.0`, wait for the publish workflow to complete, then verify the artifact exists at `quay.io/takinosh/cli-schema-mcp:v0.1.0` without any manual intervention.

**Acceptance Scenarios**:

1. **Given** no manual action after tagging, **When** `git push origin v0.1.0`, **Then** the publish workflow starts automatically and completes successfully.
2. **Given** the publish workflow has completed, **When** `oras pull quay.io/takinosh/cli-schema-mcp:v0.1.0`, **Then** the artifact extracts the full `schemas/` directory with all declared CLI versions.
3. **Given** a subsequent tag `v0.2.0` is pushed, **When** the workflow completes, **Then** `:v0.2.0` is new and `:latest` now points to the `v0.2.0` content.

---

### User Story 3 - Documentation guides operators to use OCI pull (Priority: P2)

As a cluster operator, I want to know the exact `oras pull` or container image syntax to mount the schema registry, so that I can configure the MCP server in an air-gapped deployment without guessing.

**Why this priority**: Without clear docs, users cannot discover or use the OCI path. Comes after the publish path is proven.

**Independent Test**: Follow only the README OCI pull section and the Containerfile instructions to configure `SCHEMA_REGISTRY_PATH`. Confirm the MCP server starts successfully and passes the health check.

**Acceptance Scenarios**:

1. **Given** a new operator reading the README, **When** they follow the OCI pull documentation, **Then** they can start the MCP server pointed at the pulled registry without consulting source code or maintainers.
2. **Given** the Containerfile, **When** a cluster administrator builds the container image, **Then** the OCI artifact is fetched and mounted at the path expected by `SCHEMA_REGISTRY_PATH`.

---

### Edge Cases

- What happens if the quay.io push fails mid-tag (network error)? The workflow exits non-zero; the versioned tag artifact is not published and `:latest` is not updated.
- What happens if credentials (`QUAY_USERNAME`/`QUAY_PASSWORD`) are missing or expired? The workflow fails with a clear authentication error before any push is attempted.
- What happens if `schemas/` is empty? The artifact is pushed but contains an empty archive; the MCP server startup fails with a clear error about missing schemas — this is acceptable because an empty registry is a misconfiguration, not a normal publish.
- What happens to existing `:latest` if a push of a new version fails after the versioned tag succeeds? The versioned tag is pushed first; `:latest` is pushed in a separate step. A failure between the two leaves `:latest` at the previous version, which is safe.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When a `v*` tag is pushed to the repository, the publish workflow MUST package the `schemas/` directory and push the result to `quay.io/takinosh/cli-schema-mcp` with both the version tag and `:latest`.
- **FR-002**: The OCI artifact MUST be pullable without any credentials, so that air-gapped clusters can pull without storing registry credentials on each node.
- **FR-003**: The artifact format MUST allow extraction of the `schemas/` directory tree so that `SCHEMA_REGISTRY_PATH` can point at it directly.
- **FR-004**: The publish workflow MUST fail with a non-zero exit code and leave the registry unchanged if authentication fails, packaging fails, or either push fails.
- **FR-005**: The README MUST include a section describing how to pull the OCI artifact and configure `SCHEMA_REGISTRY_PATH` to use it.
- **FR-006**: The `Containerfile` MUST show how to fetch and mount the OCI schema artifact at build time as the schema registry path.
- **FR-007**: Publishing MUST require no manual steps beyond pushing a version tag.

### Key Entities

- **OCI artifact**: The packaged `schemas/` directory stored at `quay.io/takinosh/cli-schema-mcp:<tag>`. Content is a `.tar.gz` archive with media type `application/vnd.cli-schema-mcp.schemas.v1.tar+gzip`.
- **Version tag**: A `v*` git tag (e.g. `v0.1.0`) that triggers the publish workflow.
- **`SCHEMA_REGISTRY_PATH`**: Environment variable the MCP server reads at startup to locate the schema JSON files. When set, it overrides the default `schemas/` directory in the working tree.
- **Publish workflow**: `.github/workflows/publish-schemas-oci.yml` — the GitHub Actions workflow that logs into quay.io and pushes the artifact.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After pushing a `v*` tag, the artifact is available at `quay.io/takinosh/cli-schema-mcp:<tag>` within 5 minutes of the tag push, with no manual steps.
- **SC-002**: Pulling and extracting the artifact on a machine that cannot reach GitHub produces a complete `schemas/` tree (at minimum: oc, kubectl, kustomize, podman, tkn directories, each with at least one version JSON).
- **SC-003**: The MCP server started with `SCHEMA_REGISTRY_PATH` pointing at the extracted artifact passes the health check and returns correct flag data for `oc 4.22`.
- **SC-004**: A first-time operator following only the README OCI section can pull and configure the registry in under 10 minutes.

## Assumptions

- The quay.io repository `takinosh/cli-schema-mcp` already exists and is configured for public pull (no credentials required to pull).
- `QUAY_USERNAME` and `QUAY_PASSWORD` (or a robot account token) are set as GitHub Actions repository secrets before the first tagged release.
- The `oras` CLI is the packaging tool (already in the workflow via `oras-project/setup-oras`).
- Schema signing (cosign, Sigstore) is out of scope for this spec.
- Multi-registry push (GHCR + quay.io simultaneously) is out of scope.
- A schema changelog or diff artifact is out of scope.
- The `SCHEMA_REGISTRY_PATH` env var is already supported by the MCP server settings (inherited from spec 001 assumptions; if not present it must be added as a minor server change).
