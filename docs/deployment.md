# Deployment Guide

## Local (Podman / Docker Compose)

### Quick start with Compose

```bash
podman compose up --build
```

### Manual build and run

```bash
podman build -t cli-schema-mcp .
podman run -p 5001:5001 --env-file .env cli-schema-mcp
```

Verify:

```bash
curl http://localhost:5001/health
# {"status": "healthy"}
```

### Connect an MCP client

Once the server is running, point your MCP client at it.

**Claude Code** (`~/.claude/mcp.json`):

```json
{
  "servers": {
    "cli-schema-mcp": {
      "url": "http://localhost:5001"
    }
  }
}
```

**curl (MCP JSON-RPC)**:

```bash
# List available tools
curl -s -X POST http://localhost:5001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python -m json.tool

# Call list_supported
curl -s -X POST http://localhost:5001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_supported","arguments":{}}}' \
  | python -m json.tool
```

---

## Deploying to OpenShift

The OpenShift manifests live in `deployment/openshift/` (Deployment, Service, Route, ConfigMap, Secret, BuildConfig, ImageStream, Kustomization).

```bash
# Deploy to OpenShift namespace
make deploy openshift NAMESPACE=your-project-name

# Remove deployment
make undeploy openshift
```

After deployment the route exposes the server. Connect an MCP client to the route URL:

```json
{
  "servers": {
    "cli-schema-mcp": {
      "url": "https://cli-schema-mcp-<namespace>.apps.<cluster-domain>"
    }
  }
}
```

### Air-gapped OpenShift deployment

In clusters with no internet access at build time, use the OCI artifact to embed schemas
into the image before pushing to the internal registry:

```bash
# Pull schema artifact from quay.io (needs network access once)
oras pull quay.io/takinosh/cli-schema-mcp:latest --output /tmp/schemas-pull
mkdir /opt/cli-schemas
tar -xzf /tmp/schemas-pull/schemas.tar.gz -C /opt/cli-schemas

# Build the image and pass the schema path via environment
podman build -t cli-schema-mcp .
podman run -p 5001:5001 \
  -e SCHEMA_REGISTRY_PATH=/opt/cli-schemas \
  -v /opt/cli-schemas:/opt/cli-schemas:ro \
  cli-schema-mcp
```

Or embed the schemas at image build time by following the commented `oras pull` block in
the `Containerfile`. Push the resulting image to your internal registry and update the
`deployment/openshift/` manifests to reference it.

### PostgreSQL (auth only)

PostgreSQL is only needed when `ENABLE_AUTH=True`. The default is `ENABLE_AUTH=False`
and no database is required.

If you enable auth, the OpenShift manifests **do not include a PostgreSQL deployment** —
provision it separately and set `POSTGRES_*` values:

| Option | When to Use |
|--------|------------|
| [CloudNativePG Operator](https://cloudnative-pg.io/) | Recommended — operator-managed, HA-ready |
| Managed cloud DB (RDS, Cloud SQL, Azure DB) | Hybrid or cloud deployments |
| Standalone PostgreSQL Pod | Quick testing only |

Set these in `deployment/openshift/secret.yaml`:

```yaml
POSTGRES_DB: "your-db-name"
POSTGRES_USER: "your-db-user"
POSTGRES_PASSWORD: "your-secure-password"
```

And in `deployment/openshift/configmap.yaml`:

```yaml
POSTGRES_HOST: "your-db-host"
POSTGRES_PORT: "5432"
```

---

## Container Build (`Containerfile`)

Built on Red Hat UBI 9 + Python 3.12:

| Stage | What Happens |
|-------|-------------|
| **Base image** | `registry.access.redhat.com/ubi9/python-312:latest` |
| **Dependency install** | Installs `uv`, creates venv, installs runtime deps |
| **Source copy** | Copies `cli_schema_mcp/`, `clis/`, `schemas/` into `/app` |
| **Environment** | Sets `VIRTUAL_ENV`, `PATH`, `PYTHONPATH=/app` |
| **User** | Drops to `default` (non-root) for runtime security |
| **Entrypoint** | `CMD ["/app/.venv/bin/python", "-m", "cli_schema_mcp.src.main"]` |

Port **5001** exposed via `EXPOSE 5001`.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HOST` | `localhost` | Bind address (`0.0.0.0` for containers) |
| `MCP_PORT` | `5001` | Server port |
| `MCP_TRANSPORT_PROTOCOL` | `http` | `http`, `sse`, or `streamable-http` |
| `SCHEMA_REGISTRY_PATH` | *(unset)* | Override schema directory (use with OCI pull) |
| `ENABLE_AUTH` | `False` | Enable OAuth authentication |
| `PYTHON_LOG_LEVEL` | `INFO` | Log level |
| `MCP_SSL_KEYFILE` | *(unset)* | SSL private key path |
| `MCP_SSL_CERTFILE` | *(unset)* | SSL certificate path |

---

## Testing the Deployment

```bash
# Health check
curl -f http://localhost:5001/health

# Verify schemas are loaded (should return 5 CLIs)
curl -s -X POST http://localhost:5001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_supported","arguments":{}}}' \
  | python -m json.tool

# Import validation (container)
podman run --rm cli-schema-mcp python -c "import cli_schema_mcp; print('OK')"

# SSL (if configured)
curl -k https://localhost:5001/health
```

---

## Compose Configuration

`compose.yaml` maps port 5001 to the host and overrides `MCP_HOST=0.0.0.0` so the server
binds to all interfaces inside the container (required for port forwarding).
