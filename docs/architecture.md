# Architecture

## System Architecture

```mermaid
graph TB
    subgraph "External Clients"
        A[Claude Code / AI Agent]
        B[Custom MCP Client]
        C[LangGraph / Automation]
    end

    subgraph "Network Layer"
        D[Load Balancer/Proxy]
        E[SSL Termination]
    end

    subgraph "cli-schema-mcp Server"
        subgraph "Application Layer"
            F[FastAPI Application<br/>api.py]
            G[Health Check Endpoint<br/>/health]
            H[MCP Protocol Handler<br/>/mcp]
        end

        subgraph "MCP Core"
            I[CLISchemaMCPServer<br/>mcp.py]
            J[FastMCP Instance<br/>Protocol Implementation]
            K[Tool Registry<br/>Dynamic Registration]
        end

        subgraph "Tool Layer"
            L[get_flags<br/>Flag lookup by command + version]
            M[list_subcommands<br/>Subcommand tree traversal]
            N[validate_command<br/>Hallucination rejection]
            O[detect_version<br/>Version string parsing]
            P[list_supported<br/>Registry enumeration]
            PA[get_download_info<br/>Download URLs from registration]
        end

        subgraph "Schema Registry"
            Q[schema_registry.py<br/>JSON catalog loader]
            R[schemas/<br/>oc/, kubectl/, kustomize/<br/>podman/, tkn/ ...]
        end

        subgraph "Infrastructure Layer"
            S[Configuration Management<br/>settings.py]
            T[Structured Logging<br/>pylogger.py]
            U[Error Handling<br/>Exception Management]
        end

        subgraph "Transport Layer"
            V[HTTP Transport]
            W[SSE Transport]
            X[Streamable HTTP Transport]
        end
    end

    subgraph "Build-time Only"
        Y[extractor/<br/>obtain.py, refresh.py<br/>cobra adapter]
        Z[clis/*.yaml<br/>CLI registrations]
        AA[CI: extract-schemas.yml<br/>auto-extracts on clis/ change]
    end

    subgraph "External"
        BB[Environment Variables<br/>.env]
        CC[OCI Artifact<br/>quay.io/takinosh/cli-schema-mcp]
    end

    A --> D
    B --> D
    C --> D
    D --> E
    E --> F
    F --> G
    F --> H
    H --> I
    I --> J
    J --> K
    K --> L
    K --> M
    K --> N
    K --> O
    K --> P
    L --> Q
    M --> Q
    N --> Q
    O --> Q
    P --> Q
    Q --> R
    I --> S
    I --> T
    I --> U
    F --> V
    F --> W
    F --> X
    S --> BB
    AA --> R
    Z --> AA
    Y --> AA
    CC -.->|oras pull| R

    classDef client fill:#e3f2fd
    classDef network fill:#f3e5f5
    classDef application fill:#e8f5e8
    classDef core fill:#fff3e0
    classDef tools fill:#fce4ec
    classDef registry fill:#e1f5fe
    classDef infrastructure fill:#f1f8e9
    classDef transport fill:#fef7e0
    classDef buildtime fill:#f5f5f5
    classDef external fill:#eeeeee

    class A,B,C client
    class D,E network
    class F,G,H application
    class I,J,K core
    class L,M,N,O,P tools
    class Q,R registry
    class S,T,U infrastructure
    class V,W,X transport
    class Y,Z,AA buildtime
    class BB,CC external
```

**Key architectural invariant**: The `extractor/` package is **build-time only**. It is never imported by the MCP server at runtime. Schemas are pre-extracted JSON files on the filesystem.

## Request Flow

```mermaid
flowchart TD
    A[MCP Client Request] --> B{Transport Protocol?}

    B -->|HTTP/Streamable-HTTP| C[FastAPI App<br/>api.py]
    B -->|SSE| D[SSE App<br/>create_sse_app]

    C --> E{Path?}
    D --> E

    E -->|/health| F[Health Endpoint<br/>Return Status]
    E -->|/mcp| G[MCP Request Handler<br/>FastMCP Instance]

    G --> H{MCP Method?}

    H -->|tools/list| I[Return 6 tool definitions]
    H -->|tools/call| J[Tool Router<br/>mcp.py]

    J --> K{Which Tool?}

    K -->|get_flags| L[get_flags_tool.py<br/>Load schema → filter by command]
    K -->|list_subcommands| M[list_subcommands_tool.py<br/>Load schema → return subtree]
    K -->|validate_command| N[validate_command_tool.py<br/>Parse command → check flags]
    K -->|detect_version| O[detect_version_tool.py<br/>Match version string]
    K -->|list_supported| P[list_supported_tool.py<br/>Enumerate schemas/ dirs]
    K -->|get_download_info| PA[get_download_info_tool.py<br/>Read clis/*.yaml obtain block]

    L --> Q[schema_registry.py<br/>load_schema tool version]
    M --> Q
    N --> Q
    O --> Q
    P --> Q

    Q --> R[schemas/tool/version.json<br/>Pre-extracted flag catalog]

    R --> S[Return structured response<br/>Dict with status + data]
    S --> T[Send to MCP Client]

    F --> T
    I --> T

    classDef request fill:#e3f2fd
    classDef routing fill:#f3e5f5
    classDef tools fill:#e8f5e8
    classDef registry fill:#e1f5fe
    classDef response fill:#fff3e0

    class A,B,E,H,K request
    class C,D,G,J routing
    class L,M,N,O,P tools
    class Q,R registry
    class S,T,F,I response
```

## Code Structure

```
cli-schema-mcp/
├── cli_schema_mcp/              # MCP server package (runtime)
│   ├── __init__.py
│   ├── src/
│   │   ├── main.py              # Application entry point
│   │   ├── api.py               # FastAPI app + transport setup
│   │   ├── mcp.py               # MCP server + tool registration
│   │   ├── schema_registry.py   # JSON catalog loader (lru_cache)
│   │   ├── settings.py          # Pydantic configuration
│   │   ├── oauth/               # OAuth integration (off by default)
│   │   ├── storage/             # PostgreSQL token storage (auth only)
│   │   └── tools/               # One file per MCP tool
│   │       ├── get_flags_tool.py
│   │       ├── list_subcommands_tool.py
│   │       ├── validate_command_tool.py
│   │       ├── detect_version_tool.py
│   │       ├── list_supported_tool.py
│   │       └── get_download_info_tool.py
│   └── utils/
│       └── pylogger.py          # Structured logging
│
├── extractor/                   # Build-time only — never imported by server
│   ├── cli_config.py            # YAML registration parser + ObtainConfig
│   ├── obtain.py                # Download, SHA-256 verify, unpack
│   ├── refresh.py               # Change detection + all-or-nothing publish
│   ├── main.py                  # python -m extractor <cli> <version>
│   └── adapters/
│       ├── cobra.py             # Cobra __complete + help-text extraction
│       └── help_parser.py       # Regex-based help text parser
│
├── clis/                        # CLI registrations (one YAML per CLI)
│   ├── oc.yaml
│   ├── kubectl.yaml
│   ├── kustomize.yaml
│   ├── podman.yaml
│   └── tkn.yaml
│
├── schemas/                     # Pre-extracted flag catalogs (committed)
│   ├── oc/          4.18.json … 4.22.json
│   ├── kubectl/     1.31.json … 1.35.json
│   ├── kustomize/   5.3.json … 5.5.json
│   ├── podman/      5.2.json … 5.4.json
│   └── tkn/         0.45.json, 0.46.json
│
├── tests/                       # Test suite (355 tests, 84%+ coverage)
├── .github/workflows/
│   ├── test.yml                 # Tests + coverage gate
│   ├── pre-commit.yml           # Linting, mypy, bandit
│   ├── extract-schemas.yml      # Auto-extract on clis/ change
│   └── publish-schemas-oci.yml  # Publish to quay.io on v* tag
├── Containerfile
├── pyproject.toml
└── README.md
```

## Key Components

- **`schema_registry.py`**: Loads `schemas/<tool>/<version>.json` with `lru_cache` on first access. `SCHEMA_REGISTRY_PATH` env var overrides the default `schemas/` directory (used with OCI pull for air-gapped deployments).
- **`mcp.py`**: Registers all six tools with FastMCP. Tools always return `Dict[str, Any]` with a `status` field and never raise.
- **`extractor/refresh.py`**: Entry point `python -m extractor.refresh --base <rev> --head <rev>`. Detects changed `clis/` registrations, downloads + verifies each declared version's binary, runs the extractor, and publishes `schemas/` only after all versions succeed (all-or-nothing).
- **`obtain.py`**: Downloads artifact from `artifact_url`, verifies SHA-256 against `checksum_url`, unpacks `raw`/`tar.gz`/`zip` formats with up to 3-layer unwrap.
- **`settings.py`**: Pydantic-based configuration. `ENABLE_AUTH` defaults to `False`. `SCHEMA_REGISTRY_PATH` overrides the schema directory.
- **`oauth/`**, **`storage/`**: OAuth 2.0 + PostgreSQL token storage — available but off by default. See [Authentication Guide](authentication.md).

## MCP Tools

| Tool | Input | Output |
|------|-------|--------|
| `get_flags` | `tool`, `version`, optional `flag_prefix` | List of flag objects (name, type, shorthand, default, deprecated) |
| `list_subcommands` | `tool`, `version`, optional `command_path` | List of subcommand names + descriptions |
| `validate_command` | `tool`, `version`, `command_string` | `valid` bool + list of invalid flags if any |
| `detect_version` | `tool` | Matched version string, or `binary_not_found` with `install_hint` when the CLI is not in PATH |
| `list_supported` | — | Dict of supported tools → version list |
| `get_download_info` | `tool`, optional `version` | Download URLs, archive format, binary path, and install guidance from `clis/<tool>.yaml` — no binary or network required |

## HTTP Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — `{"status": "healthy"}` |
| `POST` | `/mcp` | MCP JSON-RPC (tools/list, tools/call) |
| `GET` | `/.well-known/oauth-protected-resource` | RFC 8414 metadata (auth only) |
| `GET` | `/.well-known/oauth-authorization-server` | RFC 8414 metadata (auth only) |

OAuth routes (`/auth/*`) are registered only when `ENABLE_AUTH=True`.
