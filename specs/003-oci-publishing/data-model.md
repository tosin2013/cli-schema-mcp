# Data Model: OCI Artifact Publishing

## OCI Artifact

The schema registry is published as a single OCI artifact (one manifest, one layer) to `quay.io/takinosh/cli-schema-mcp`.

| Field | Value |
|-------|-------|
| Registry | `quay.io` |
| Repository | `takinosh/cli-schema-mcp` |
| Layer media type | `application/vnd.cli-schema-mcp.schemas.v1.tar+gzip` |
| Layer content | `schemas.tar.gz` — a gzip-compressed tar of the `schemas/` directory tree |
| Tags | `v<semver>` (immutable, one per release) and `latest` (mutable, always points to newest release) |

### Artifact contents

When extracted, the artifact produces the same directory tree that lives under `schemas/` in the repository:

```text
schemas/
├── oc/
│   ├── 4.18.json
│   ├── 4.19.json
│   ├── 4.20.json
│   ├── 4.21.json
│   └── 4.22.json
├── kubectl/
│   └── *.json  (one per declared version)
├── kustomize/
│   └── *.json
├── podman/
│   └── *.json
└── tkn/
    └── *.json
```

The JSON files are the pre-extracted flag catalogs committed to the repository. The artifact is a snapshot of the repository's `schemas/` at the tagged commit; it does not contain any additional metadata files.

## Release

A release is triggered by pushing a `v*` git tag. It is not a stored entity — it is an event that produces an OCI artifact. The tag name becomes the versioned tag on the artifact.

| Field | Description |
|-------|-------------|
| `git_tag` | The `v*` tag that triggered the publish (e.g. `v0.1.0`) |
| `artifact_tag` | Same as `git_tag` — pushed as `:v0.1.0` |
| `latest_tag` | `:latest` — updated to point at this release |
| `published_at` | Timestamp of successful workflow completion |

## Server configuration

| Entity | Description |
|--------|-------------|
| `SCHEMA_REGISTRY_PATH` | Env var read by the MCP server at startup. When set, overrides the default `schemas/` directory. Points at the local path where the OCI artifact was extracted. |

The server reads `SCHEMA_REGISTRY_PATH` via `cli_schema_mcp.src.settings.Settings`. No code change is needed — the field already exists.

## Containerfile integration

The Containerfile gains an `oras pull` + `tar` layer that fetches the OCI artifact at build time and sets `SCHEMA_REGISTRY_PATH` via `ENV`. The result is a self-contained image that carries the schema registry without internet access at runtime.

```text
# (example — exact syntax in quickstart.md)
RUN oras pull quay.io/takinosh/cli-schema-mcp:latest \
      --output /schemas-archive && \
    tar -xzf /schemas-archive/schemas.tar.gz -C /schemas && \
    rm -rf /schemas-archive
ENV SCHEMA_REGISTRY_PATH=/schemas
```
