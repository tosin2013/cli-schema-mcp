# Tutorial: Using cli-schema-mcp

Two tutorials in one page:

1. **[Using the MCP server](#using-the-mcp-server)** — start the server, call the tools, see real outputs
2. **[Adding your first CLI](#adding-your-first-cli)** — register a new CLI in 5 minutes

---

## Using the MCP server

### Prerequisites

```bash
git clone https://github.com/tosin2013/cli-schema-mcp
cd cli-schema-mcp
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Start the server

```bash
cli-schema-mcp
# or: python -m cli_schema_mcp.src.main
```

```
INFO  Server starting on http://localhost:5001
INFO  MCP endpoint: http://localhost:5001/mcp
INFO  Health:       http://localhost:5001/health
```

Verify it's running:

```bash
curl http://localhost:5001/health
# {"status": "healthy"}
```

### Connect from Claude Code

Add the server to your Claude Code MCP configuration (`~/.claude/mcp.json`):

```json
{
  "servers": {
    "cli-schema-mcp": {
      "url": "http://localhost:5001"
    }
  }
}
```

Claude Code will now have access to all six tools when you work in any project.

---

### Tool: `list_supported`

Enumerate all CLIs and versions in the registry.

```python
# Python (direct import for testing)
from cli_schema_mcp.src.tools.list_supported_tool import list_supported
list_supported()
```

**Output:**

```json
{
  "status": "success",
  "total_tools": 5,
  "total_schemas": 20,
  "tools": {
    "kubectl": ["1.31", "1.32", "1.33", "1.34", "1.35"],
    "kustomize": ["5.3", "5.4", "5.5"],
    "oc": ["4.18", "4.19", "4.20", "4.21", "4.22"],
    "podman": ["5.2", "5.3", "5.4"],
    "tkn": ["0.45", "0.46"]
  }
}
```

**When an agent calls this**: Before generating any CLI command, the agent calls `list_supported` to know which tools and versions have schema coverage. If the tool or version isn't listed, the agent falls back to its training knowledge (with appropriate uncertainty).

---

### Tool: `list_subcommands`

Browse the command tree without running the binary.

```python
from cli_schema_mcp.src.tools.list_subcommands_tool import list_subcommands
list_subcommands("oc", "4.22", "rollout")
```

**Output:**

```json
{
  "status": "success",
  "tool": "oc",
  "version": "4.22",
  "matched_version": "4.22",
  "parent": "rollout",
  "subcommands": [
    "cancel", "history", "latest", "pause",
    "restart", "resume", "retry", "status", "undo"
  ],
  "message": "Found 9 subcommands under 'rollout'"
}
```

Call with no `parent` to get the top-level subcommands. Use this to build the right command path before looking up flags.

---

### Tool: `get_flags`

Return all flags for a specific command and version.

```python
from cli_schema_mcp.src.tools.get_flags_tool import get_flags
get_flags("oc", "4.22", "rollout restart")
```

**Output (truncated — `oc rollout restart` has many flags):**

```json
{
  "status": "success",
  "tool": "oc",
  "version": "4.22",
  "command": "rollout restart",
  "flags": [
    {
      "name": "--dry-run",
      "shorthand": null,
      "type": "string",
      "default": "none",
      "description": "Must be 'none', 'server', or 'client'.",
      "deprecated": false
    },
    {
      "name": "--filename",
      "shorthand": "-f",
      "type": "stringArray",
      "default": null,
      "description": "Filename, directory, or URL to files identifying the resource to get from a server.",
      "deprecated": false
    },
    {
      "name": "--selector",
      "shorthand": "-l",
      "type": "string",
      "default": null,
      "description": "Selector (label query) to filter on.",
      "deprecated": false
    },
    {
      "name": "--timeout",
      "shorthand": null,
      "type": "duration",
      "default": "0s",
      "description": "The length of time to wait before giving up.",
      "deprecated": false
    }
  ]
}
```

Each flag object carries `name`, `shorthand`, `type`, `default`, `description`, and `deprecated`. An agent uses this to build a command with only real flags.

---

### Tool: `validate_command`

Check a complete command string against the schema. This is the **hallucination firewall**.

#### Valid command

```python
from cli_schema_mcp.src.tools.validate_command_tool import validate_command
validate_command("oc", "4.22", "oc rollout restart deployment/myapp -n prod")
```

```json
{
  "status": "success",
  "tool": "oc",
  "version": "4.22",
  "matched_version": "4.22",
  "command_string": "oc rollout restart deployment/myapp -n prod",
  "subcommand_context": "'oc rollout restart'",
  "valid": true,
  "errors": [],
  "message": "Command is valid"
}
```

#### Invalid command — hallucinated flag

```python
validate_command("oc", "4.22", "oc rollout restart deployment/myapp --force")
```

```json
{
  "status": "success",
  "tool": "oc",
  "version": "4.22",
  "matched_version": "4.22",
  "command_string": "oc rollout restart deployment/myapp --force",
  "subcommand_context": "'oc rollout restart'",
  "valid": false,
  "errors": [
    "--force is not a valid flag for 'oc rollout restart' in version 4.22"
  ],
  "message": "1 invalid flag(s) found"
}
```

`--force` does not exist on `oc rollout restart` — the agent must revise the command before executing it. This is the core value: the rejection happens **before** the command runs in your cluster.

**Typical agent loop:**

```
User: "Restart my oc deployment in namespace prod"

Agent → validate_command("oc rollout restart deployment/myapp --force")
     ← valid: false, errors: ["--force is not valid"]

Agent → get_flags("oc", "4.22", "rollout restart")
     ← flags: [...no --force listed...]

Agent → validate_command("oc rollout restart deployment/myapp -n prod")
     ← valid: true

Agent → presents: `oc rollout restart deployment/myapp -n prod`
```

---

### Tool: `detect_version`

Parse the locally-installed CLI version from `version_command` output. Requires the binary in PATH.

```python
from cli_schema_mcp.src.tools.detect_version_tool import detect_version
detect_version("oc")   # runs `oc version --client` and parses it
```

```json
{
  "status": "success",
  "tool": "oc",
  "detected_version": "4.22",
  "raw_output": "Client Version: 4.22.1",
  "message": "Detected version 4.22"
}
```

When the binary is **not installed** (common in containerized deployments where the MCP server has no CLIs), `detect_version` returns `binary_not_found` with install guidance:

```json
{
  "status": "binary_not_found",
  "tool": "oc",
  "message": "'oc' is not installed in this environment.",
  "install_hint": "Download from https://mirror.openshift.com/pub/openshift-v4/clients/ or run: dnf install openshift-clients",
  "suggestion": "Call get_download_info('oc') for version-specific download URLs, or ask the user to install the CLI before retrying."
}
```

---

### Tool: `get_download_info`

Return download URLs and install guidance from the CLI registration — no binary or network
required. Designed for containerized deployments where the agent needs to guide the user.

```python
from cli_schema_mcp.src.tools.get_download_info_tool import get_download_info
get_download_info("oc", "4.22")
```

```json
{
  "status": "success",
  "tool": "oc",
  "upstream_repo": "https://github.com/openshift/oc",
  "versions": [
    {
      "version": "4.22",
      "artifact_url": "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-4.22/openshift-client-linux.tar.gz",
      "checksum_url": "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-4.22/sha256sum.txt",
      "format": "tar.gz",
      "binary": "oc"
    }
  ],
  "install_notes": "Download the artifact, verify the checksum, and place the binary in your PATH."
}
```

For system-package CLIs (like `nmstate`) with no automated download:

```json
{
  "status": "success",
  "tool": "nmstate",
  "install_method": "system_package",
  "install_notes": "Install via your package manager (e.g. dnf install nmstate) or see https://github.com/nmstate/nmstate"
}
```

**Containerized agent workflow:**

```
detect_version("oc") → binary_not_found + install_hint
get_download_info("oc", "4.22") → artifact_url, checksum_url, install_notes
Agent → presents download URL and instructions to user
User installs oc in their environment
Agent → retries the original command
```

---

## Adding your first CLI

Register a new CLI in the schema registry. No Python code required — CI handles extraction automatically.

### Step 1: Create the registration file

```yaml
# clis/flux.yaml
name: flux
display_name: "Flux CLI"
description: "CLI for Flux GitOps toolkit"
binary: flux
adapter: cobra
versions:
  - "2.3"
  - "2.4"
version_command: "flux version"
version_parse: "{version}"
upstream_repo: "https://github.com/fluxcd/flux2"
maintainers:
  - "your-github-username"
obtain:
  version_url: "https://api.github.com/repos/fluxcd/flux2/releases?per_page=10"
  version_match: "v({version}\\.\\d+)[^\"-]"
  artifact_url: "https://github.com/fluxcd/flux2/releases/download/v{resolved}/flux_{resolved}_linux_amd64.tar.gz"
  checksum_url: "https://github.com/fluxcd/flux2/releases/download/v{resolved}/flux_{resolved}_checksums.txt"
  format: "tar.gz"
  binary: "flux"
```

**Key fields:**

| Field | Purpose |
|-------|---------|
| `adapter: cobra` | Cobra `__complete` extractor — works for any Cobra CLI |
| `versions` | Minor versions to maintain schema catalogs for |
| `obtain.version_url` | Fetch to resolve patch tag (set `version_url` + `version_match` together) |
| `obtain.version_match` | Regex with **one capture group** — the group is `{resolved}` |
| `obtain.artifact_url` | Download URL using `{version}` and/or `{resolved}` tokens |
| `obtain.checksum_url` | SHA-256 checksum file — verified before the binary runs |
| `obtain.binary` | Binary name inside the archive (use member path for nested archives) |

### Step 2: Test locally

```bash
# Refresh schemas for the changed registration
python -m extractor.refresh --base HEAD --head WORKTREE

# Or extract a single version if the binary is in PATH
python -m extractor flux 2.4

# Verify
cat schemas/flux/2.4.json | python -m json.tool | head -10
```

### Step 3: Open a Pull Request

```bash
git checkout -b feat/add-flux
git add clis/flux.yaml
git commit -m "feat: add flux CLI registration (2.3, 2.4)"
git push origin feat/add-flux
```

CI (`extract-schemas.yml`) automatically:
1. Detects `clis/flux.yaml` as a new registration
2. Downloads and verifies the binary for each declared version
3. Runs the Cobra extractor
4. Commits `schemas/flux/2.3.json` and `schemas/flux/2.4.json` to the branch

The reviewer sees the schema diff and approves. No manual extraction step.

---

## What's next

| Topic | Link |
|-------|-------|
| Full `obtain` block field reference | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Architecture and schema registry | [Architecture](architecture.md) |
| CI workflows | [CI/CD](ci-cd.md) |
| Deploying the server | [Deployment](deployment.md) |
| Air-gapped OCI deployment | [README — Air-gapped section](../README.md#air-gapped-deployment-oci) |
