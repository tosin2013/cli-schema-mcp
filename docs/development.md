# Development Guide

## Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) (fast Python package installer and resolver)
- make (macOS: `xcode-select --install`, Linux: `sudo apt install make` or `sudo dnf install make`)
- [Podman](https://podman.io/docs/installation) and [podman-compose](https://github.com/containers/podman-compose#installation) (optional — for containerised deployment and local PostgreSQL)

## Setup

1. **Install uv (if not already installed):**

   ```bash
   # On macOS/Linux:
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # On macOS using brew:
   brew install uv

   # On Windows:
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Clone the repository:**

   ```bash
   git clone https://github.com/tosin2013/cli-schema-mcp
   cd cli-schema-mcp
   ```

3. **Create and activate a virtual environment:**

   ```bash
   uv venv
   source .venv/bin/activate   # macOS/Linux
   .venv\Scripts\activate      # Windows
   ```

4. **Install the package and development dependencies:**

   ```bash
   uv pip install -e ".[dev]"
   ```

5. **Install pre-commit hooks:**

   ```bash
   pre-commit install
   ```

6. **Configure environment variables:**

   ```bash
   cp .env.example .env
   # ENABLE_AUTH=False by default — no SSO provider needed to start
   ```

7. **Run the server:**

   ```bash
   # Console script
   cli-schema-mcp

   # Or via Python module
   python -m cli_schema_mcp.src.main
   ```

## Verify Installation

```bash
# Health check
curl http://localhost:5001/health
# {"status": "healthy"}

# List all supported CLIs and versions
curl -s -X POST http://localhost:5001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_supported","arguments":{}}}' \
  | python -m json.tool

# Validate a command (hallucination check)
curl -s -X POST http://localhost:5001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"validate_command","arguments":{"tool":"oc","version":"4.22","command_string":"oc rollout restart deployment/myapp -n prod"}}}' \
  | python -m json.tool
```

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HOST` | `localhost` | Server bind address (`0.0.0.0` for containers) |
| `MCP_PORT` | `5001` | Server port (1024-65535) |
| `MCP_TRANSPORT_PROTOCOL` | `http` | `http`, `sse`, or `streamable-http` |
| `MCP_HOST_ENDPOINT` | `http://localhost:5001` | Public URL (used in OAuth discovery) |
| `MCP_SSL_KEYFILE` | `None` | SSL private key file path |
| `MCP_SSL_CERTFILE` | `None` | SSL certificate file path |
| `SCHEMA_REGISTRY_PATH` | *(unset)* | Override schema directory for air-gapped OCI deployments |
| `PYTHON_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `ENVIRONMENT` | `development` | Deployment environment identifier |
| `ENABLE_AUTH` | `False` | Enable OAuth authentication |
| `USE_EXTERNAL_BROWSER_AUTH` | `False` | Browser-based OAuth for local dev |
| `CORS_ENABLED` | `False` | Enable CORS middleware |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins |

See the [Authentication Guide](authentication.md) for `SSO_*` and `POSTGRES_*` variables.

## Schema Development Workflow

### Working with CLI registrations

Registrations live in `clis/*.yaml`. Each file declares one CLI with an `obtain` block
that tells CI how to download, verify, and extract its binary.

```bash
# After editing or adding a clis/*.yaml file, refresh schemas locally:
python -m extractor.refresh --base HEAD --head WORKTREE

# Or extract a single version (binary must be in PATH):
python -m extractor oc 4.22

# Verify the output:
cat schemas/oc/4.22.json | python -m json.tool | head -20
```

### Extractor package

The `extractor/` package is **build-time only** — it is never imported by the server at
runtime. The key entry points:

```bash
# Refresh changed registrations (used by CI):
python -m extractor.refresh --base <rev> --head <rev> [--no-push]

# Extract a single CLI version:
python -m extractor <cli-name> <version>
```

`extractor.refresh` options:

| Flag | Description |
|------|-------------|
| `--base` | Base git revision to compare against |
| `--head` | Head revision or `WORKTREE` (default) |
| `--no-push` | Report catalog differences instead of publishing (fork PR mode) |
| `--clis-dir` | Path to CLI registrations (default: `clis/`) |
| `--schemas-dir` | Path to output catalogs (default: `schemas/`) |

Exit codes: `0` = success, `1` = extraction failure, `2` = catalogs differ (no-push mode).

### Schema registry

The server reads `schemas/<tool>/<version>.json` at startup via `schema_registry.py`.
To add a new CLI tool to the live server during development:

1. Add `clis/<name>.yaml` with an `obtain` block
2. Run `python -m extractor <name> <version>` (binary in PATH) or `python -m extractor.refresh`
3. Restart the server — it picks up the new JSON on startup

## Running Tests

```bash
# Run all tests
pytest

# With coverage (80% minimum enforced in CI)
pytest --cov=cli_schema_mcp --cov-report=html --cov-report=term

# Specific test files
pytest tests/test_tools.py -v        # MCP tool tests (get_flags, validate_command, etc.)
pytest tests/test_schema_registry.py -v
pytest tests/test_obtain.py -v       # Extractor download + checksum + unpack
pytest tests/test_refresh.py -v      # Extractor change detection + publish
pytest tests/test_extractor.py -v
pytest tests/test_settings.py -v
pytest tests/test_api.py -v
pytest tests/test_mcp.py -v

# Verbose / quiet
pytest -v
pytest -q
pytest --tb=short
```

### Test Suite Overview

| Test File | What It Covers |
|-----------|---------------|
| `test_tools.py` | All 5 MCP tools (get_flags, list_subcommands, validate_command, detect_version, list_supported) |
| `test_schema_registry.py` | Schema loading, caching, path resolution |
| `test_obtain.py` | Token fill, SHA-256 verify, raw/tar.gz/zip unpack |
| `test_refresh.py` | Change detection, all-or-nothing publish, no-push mode, version retirement |
| `test_extractor.py` | Extractor CLI entry point |
| `test_settings.py` | Configuration and environment variable validation |
| `test_mcp.py` | MCP server initialisation and tool registration |
| `test_api.py` | FastAPI endpoints and health check |
| `test_main.py` | Application entry point |
| `test_oauth_*.py` | OAuth controller, handler, and service |
| `test_storage_*.py` | Storage initialisation and service |
| `test_basic.py` | Integration and package structure |
| `test_utils.py` | Utility and logging |

## Code Quality

```bash
# Run all pre-commit checks (ruff, mypy, pydocstyle, bandit, yaml, json)
pre-commit run --all-files

# Lint and format with Ruff
ruff check .
ruff check . --fix
ruff format .

# Type checking
mypy cli_schema_mcp/

# Docstring validation
pydocstyle cli_schema_mcp/ --convention=google

# Security scan
bandit -r cli_schema_mcp/
```

## Authentication

By default `ENABLE_AUTH=False` — no SSO provider is needed for local development.
When you are ready to test the OAuth flow, see the [Authentication Guide](authentication.md).

## Makefile Targets

```bash
make help       # Show all targets
make install    # Install dependencies + pre-commit hooks
make test       # Run test suite
make lint       # Run linters
make format     # Format code
make coverage   # Generate coverage report
make pre-commit # Run pre-commit hooks
make local      # Run server locally
```
