# Research: OCI Artifact Publishing

## 1. OCI artifact format for schema directories

- **Decision**: Package `schemas/` as a `.tar.gz` archive with a custom media type `application/vnd.cli-schema-mcp.schemas.v1.tar+gzip`, pushed with `oras push`. The archive is a single layer; the consumer extracts it and points `SCHEMA_REGISTRY_PATH` at the result.
- **Rationale**: ORAS (OCI Registry As Storage) is already in the workflow and is the canonical tool for pushing arbitrary artifacts to OCI registries. A single tar layer is simpler than per-file layers for a directory of JSON files. A custom media type makes the artifact self-describing.
- **Alternatives considered**: Pushing each JSON file as a separate layer — rejected because it complicates extraction and increases manifest size. Using a container image (`FROM scratch` + COPY) — rejected because it adds a container runtime dependency for consumers who only need the schemas.

## 2. Registry: quay.io/takinosh/cli-schema-mcp

- **Decision**: `quay.io/takinosh/cli-schema-mcp` is the registry target. Decided by the maintainer on 2026-10-14.
- **Rationale**: quay.io is the Red Hat-hosted container registry, aligning with the Red Hat portfolio integration goal (spec 004). A personal quay.io namespace (`takinosh`) is used for Phase 3; migration to `RedHatOfficial` is a future step once Red Hat BU alignment (spec 004) is settled.
- **Alternatives considered**: GHCR (`ghcr.io/tosin2013/...`) — the existing workflow targeted this; rejected because quay.io is the standard for Red Hat artifacts. Docker Hub — rejected for the same reason.

## 3. Tag strategy: versioned + latest

- **Decision**: Each `v*` release pushes both `:<version-tag>` and `:latest`. Both pushes happen in sequence; `:latest` is pushed second so a failure between them leaves `:latest` at the previous version (safe).
- **Rationale**: Operators need a stable `:latest` for simple pull-and-run deployments, but pinned version tags for reproducible air-gapped environments. Pushing both in one workflow step is the standard OCI pattern.
- **Alternatives considered**: Only versioned tags — rejected because it forces every operator to look up the latest version before pulling, increasing friction. Floating tags only — rejected because they cannot be used in reproducible air-gapped images.

## 4. Authentication: QUAY_USERNAME / QUAY_PASSWORD secrets

- **Decision**: Use `QUAY_USERNAME` and `QUAY_PASSWORD` (robot account recommended) as GitHub Actions repository secrets. `oras login quay.io` uses these before pushing.
- **Rationale**: Robot accounts on quay.io can be scoped to push-only for the specific repository, reducing blast radius if credentials are compromised. Repository secrets in GitHub Actions are encrypted and not exposed in logs.
- **Alternatives considered**: Using `GITHUB_TOKEN` (like the GHCR approach) — not possible for quay.io which requires an external credential. OIDC federation — quay.io does not natively support GitHub Actions OIDC at this time.

## 5. SCHEMA_REGISTRY_PATH: already supported

- **Decision**: `SCHEMA_REGISTRY_PATH` is already a field in `cli_schema_mcp/src/settings.py` (confirmed in Settings class). No server code change is required.
- **Rationale**: The server was designed with air-gapped OCI distribution in mind from spec 001. The env var exists; using it requires only documentation and Containerfile updates.
- **Alternatives considered**: Adding a new CLI flag — rejected because the env var already exists and is the idiomatic configuration method for containerized deployments.

## 6. Public pull (no credentials for consumers)

- **Decision**: The quay.io repository MUST be configured for public pull access. quay.io allows this via repository visibility settings (public vs. private). Push requires credentials; pull does not.
- **Rationale**: Air-gapped deployments require pull without storing credentials on each cluster node. A public repository eliminates the credential management burden for consumers.
- **Alternatives considered**: Authenticated pull — rejected because it adds operational complexity (secret distribution across nodes) for schemas that are not sensitive data.

## 7. Containerfile integration

- **Decision**: Add a `RUN oras pull ... && tar -xzf` layer to the Containerfile showing how to embed the schemas at image build time. Set `SCHEMA_REGISTRY_PATH` to the extracted path via `ENV`.
- **Rationale**: Operators building their own images (e.g., for air-gapped OCP registries) need a concrete example. The Containerfile is the natural place for this.
- **Alternatives considered**: Init container sidecar — rejected because it adds runtime complexity; embedding at build time is simpler for the targeted air-gapped use case.

## 8. Workflow trigger: `v*` tags only

- **Decision**: The publish workflow triggers only on `push: tags: "v*"`. It does not run on push to branches or PRs.
- **Rationale**: Schema publications should be deliberate releases, not automatic on every push. This matches the standard GitHub release workflow pattern.
- **Alternatives considered**: Trigger on main branch push — rejected because it would publish a new `:latest` on every dependency bump or formatting fix, polluting the release history.
