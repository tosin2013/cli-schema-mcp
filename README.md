# cli-schema-mcp

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/tosin2013/cli-schema-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/tosin2013/cli-schema-mcp/actions/workflows/test.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A vendor-neutral, community-maintained MCP server that provides version-pinned CLI flag schemas to AI agents. When the schema server is active, `validate_command` rejects hallucinated flags for supported CLI tools and versions — the AI never gets a chance to suggest a flag that isn't in the schema.

## Supported CLIs

| CLI | Versions | Adapter |
|-----|----------|---------|
| `oc` (OpenShift CLI) | 4.18 – 4.22 | Cobra |
| `kubectl` | 1.31 – 1.35 | Cobra |
| `kustomize` | 5.3 – 5.5 | Cobra |
| `podman` | 5.2 – 5.4 | Cobra |
| `tkn` (Tekton CLI) | 0.45 – 0.46 | Cobra |

Adding a new CLI requires only a YAML config file — no Python code changes.

## MCP Tools

| Tool | Description |
|------|-------------|
| `get_flags` | Return all flags for a CLI command and version |
| `list_subcommands` | List available subcommands for a CLI |
| `validate_command` | Reject commands with hallucinated flags |
| `detect_version` | Identify the CLI version from output |
| `list_supported` | List all supported CLIs and versions |

## Quick Start

```bash
git clone https://github.com/tosin2013/cli-schema-mcp
cd cli-schema-mcp
make install        # creates venv, installs deps + pre-commit hooks
make local          # starts server on localhost:5001
```

Verify in another terminal:

```bash
curl http://localhost:5001/health
```

<details>
<summary>Manual setup (without Make)</summary>

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pre-commit install
cp .env.example .env
cli-schema-mcp
curl http://localhost:5001/health
```

</details>

## Adding a New CLI

Create `clis/<name>.yaml` with one `obtain` block — no Python changes needed:

```yaml
name: tkn
display_name: "Tekton CLI"
binary: tkn
adapter: cobra
versions:
  - "0.37"
  - "0.38"
version_command: "tkn version"
version_parse: "Client version: {version}"
upstream_repo: "https://github.com/tektoncd/cli"
maintainers:
  - "your-github-username"
obtain:
  artifact_url: "https://github.com/tektoncd/cli/releases/download/v{version}/tkn_Linux_x86_64.tar.gz"
  checksum_url: "https://github.com/tektoncd/cli/releases/download/v{version}/checksums.txt"
  format: "tar.gz"
  binary: "tkn"
```

When a `clis/` file is added or modified in a PR, CI automatically downloads each declared
version, verifies its SHA-256 checksum, extracts the schema, and commits the catalog — no
manual extraction step required.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full field reference and the `obtain` block
documentation.

## Schema Extraction

Schemas are pre-extracted at contribution time, not at query time. The MCP server itself
never downloads or runs a CLI binary.

```bash
# Refresh schemas for changed registrations locally
python -m extractor.refresh --base HEAD --head WORKTREE

# Extract a single CLI version (binary must be in PATH)
python -m extractor oc 4.22
```

## Air-gapped deployment (OCI)

The schema registry is published as an OCI artifact to
`quay.io/takinosh/cli-schema-mcp` on every tagged release. Pull it on any
machine that can reach quay.io — no internet access to GitHub required at
runtime.

```bash
# Install oras (https://oras.land)
# brew install oras  |  apt install oras  |  see https://oras.land/docs/installation

# Pull the latest schema registry
mkdir /tmp/schemas-pull
oras pull quay.io/takinosh/cli-schema-mcp:latest --output /tmp/schemas-pull

# Extract
mkdir /opt/cli-schemas
tar -xzf /tmp/schemas-pull/schemas.tar.gz -C /opt/cli-schemas

# Start the MCP server against the pulled registry
SCHEMA_REGISTRY_PATH=/opt/cli-schemas cli-schema-mcp
```

Pin to a specific release for reproducible air-gapped environments:

```bash
oras pull quay.io/takinosh/cli-schema-mcp:v0.1.1 --output /tmp/schemas-pull
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HOST` | `localhost` | Server bind address |
| `MCP_PORT` | `5001` | Server port |
| `MCP_TRANSPORT_PROTOCOL` | `http` | `http`, `sse`, or `streamable-http` |
| `ENABLE_AUTH` | `False` | Enable OAuth authentication |
| `SCHEMA_REGISTRY_PATH` | *(unset)* | Override schema directory (use with OCI pull) |

See [docs/authentication.md](docs/authentication.md) for OAuth setup.

## Documentation

| Guide | Description |
|-------|-------------|
| [Contributing](CONTRIBUTING.md) | Adding CLIs, development workflow, PR process |
| [Development](docs/development.md) | Setup, running locally, testing |
| [Deployment](docs/deployment.md) | Podman, OpenShift, container configuration |
| [Authentication](docs/authentication.md) | OAuth setup and troubleshooting |

## Contributing

```bash
git clone https://github.com/tosin2013/cli-schema-mcp.git
cd cli-schema-mcp
make install

git checkout -b feat/add-my-cli
# Add clis/my-cli.yaml
make lint && make test
git commit -m "feat: add my-cli schema"
git push origin feat/add-my-cli
```

Open a PR — CI will extract the schema automatically.

## License

[Apache 2.0](LICENSE)
