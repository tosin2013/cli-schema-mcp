# Publish Contract

The publish workflow is the operator-facing contract. It defines what is pushed, when, and what consumers can rely on.

## Trigger

```text
git push origin <tag>   # where <tag> matches v*
```

The workflow fires automatically. No other action is required from the maintainer.

## Published artifact

| Property | Value |
|----------|-------|
| Registry | `quay.io` |
| Repository | `takinosh/cli-schema-mcp` |
| Versioned tag | `:<git-tag>` (e.g. `:v0.1.0`) |
| Latest tag | `:latest` |
| Layer content | `schemas.tar.gz` with media type `application/vnd.cli-schema-mcp.schemas.v1.tar+gzip` |

The artifact is publicly pullable without credentials.

## Consumer pull contract

```text
# Pull and extract (any machine that can reach quay.io)
oras pull quay.io/takinosh/cli-schema-mcp:v0.1.0 --output /tmp/schemas-pull
tar -xzf /tmp/schemas-pull/schemas.tar.gz -C /opt/cli-schemas

# Use with the MCP server
SCHEMA_REGISTRY_PATH=/opt/cli-schemas cli-schema-mcp
```

After extraction, the directory at `SCHEMA_REGISTRY_PATH` contains:

```text
<SCHEMA_REGISTRY_PATH>/
├── oc/         — one JSON per declared version
├── kubectl/    — one JSON per declared version
├── kustomize/  — one JSON per declared version
├── podman/     — one JSON per declared version
└── tkn/        — one JSON per declared version
```

Each JSON file is the pre-extracted flag catalog for that tool and version, identical to what is committed in the repository at the same tag.

## Guarantees

- `:latest` always points to the most recent successfully published version.
- Versioned tags are immutable once pushed.
- A failed publish (network error, credential expiry, packaging failure) leaves both tags unchanged.
- `:latest` is pushed only after the versioned tag succeeds; a failure between the two leaves `:latest` at its previous version.

## Required secrets

| Secret | Description |
|--------|-------------|
| `QUAY_USERNAME` | quay.io username or robot account name |
| `QUAY_PASSWORD` | quay.io password or robot account token |

These must be set in GitHub repository secrets before the first tagged release.
