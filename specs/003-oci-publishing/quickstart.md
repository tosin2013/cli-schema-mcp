# Quickstart: OCI Artifact Publishing

Validate the publish and pull behavior locally before tagging a release.

## Prerequisites

- `oras` CLI installed locally (`brew install oras` or `apt install oras`)
- Access to `quay.io/takinosh/cli-schema-mcp` (public pull, no auth needed for pull)
- Repository secrets `QUAY_USERNAME` and `QUAY_PASSWORD` set in GitHub Actions

## 1. Verify secrets are set

In GitHub repository Settings → Secrets → Actions, confirm both `QUAY_USERNAME` and `QUAY_PASSWORD` exist. The workflow will fail to authenticate without them.

## 2. Trigger a publish

```bash
# From the repository root
git tag v0.1.0
git push origin v0.1.0
```

Watch the `Publish schemas OCI` workflow run at:
`https://github.com/tosin2013/cli-schema-mcp/actions`

Expected: both steps (`Log in to quay.io` and `Package and push schemas`) show green.

## 3. Pull and inspect the artifact

```bash
# Create a temp directory
mkdir /tmp/cli-schema-pull

# Pull the artifact (no credentials needed for public repo)
oras pull quay.io/takinosh/cli-schema-mcp:v0.1.0 --output /tmp/cli-schema-pull

# Extract
mkdir /tmp/cli-schemas
tar -xzf /tmp/cli-schema-pull/schemas.tar.gz -C /tmp/cli-schemas

# Verify structure
ls /tmp/cli-schemas/
# Expected: oc  kubectl  kustomize  podman  tkn

cat /tmp/cli-schemas/oc/4.22.json | python -m json.tool | head -10
# Expected: valid JSON with "name": "oc", "version": "4.22", non-empty subcommands
```

## 4. Run the MCP server against the pulled registry

```bash
# Install dependencies (if not already done)
uv pip install -e ".[dev]"

# Start the server pointing at the extracted schemas
SCHEMA_REGISTRY_PATH=/tmp/cli-schemas cli-schema-mcp

# In another terminal, verify
curl http://localhost:5001/health
# Expected: {"status": "ok"}
```

## 5. Verify :latest is updated

```bash
oras manifest fetch quay.io/takinosh/cli-schema-mcp:latest | python -m json.tool
# The digest should match the v0.1.0 manifest digest
```

## 6. Test Containerfile integration

```bash
# Build the image (pulls OCI artifact at build time)
podman build -t cli-schema-mcp-air-gapped .

# Run without any network access to GitHub schemas
podman run --network=none -p 5001:5001 cli-schema-mcp-air-gapped

# Verify from host
curl http://localhost:5001/health
```

Expected: the server starts and responds correctly using the embedded schema registry.

## Field references

See [data-model.md](data-model.md) for artifact structure and [contracts/publish-contract.md](contracts/publish-contract.md) for the full pull API and guarantee details.
