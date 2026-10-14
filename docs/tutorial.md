# Adding Your First CLI in 5 Minutes

Register a new CLI in the schema registry. By the end you will have a working
registration that CI automatically extracts into a flag catalog — no Python code
required.

**Prerequisites** — the server runs locally:

```bash
git clone https://github.com/tosin2013/cli-schema-mcp
cd cli-schema-mcp
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

---

## Step 1: Create the registration file

Create `clis/tkn.yaml` (Tekton CLI is used here as an example — skip if it already exists):

```yaml
name: tkn
display_name: "Tekton CLI"
description: "CLI for Tekton Pipelines and related resources"
binary: tkn
adapter: cobra
versions:
  - "0.45"
  - "0.46"
version_command: "tkn version"
version_parse: "Client version: {version}"
upstream_repo: "https://github.com/tektoncd/cli"
maintainers:
  - "your-github-username"
obtain:
  version_url: "https://api.github.com/repos/tektoncd/cli/releases?per_page=10"
  version_match: "v({version}\\.\\d+)[^\"-]"
  artifact_url: "https://github.com/tektoncd/cli/releases/download/v{resolved}/tkn_{resolved}_Linux_x86_64.tar.gz"
  checksum_url: "https://github.com/tektoncd/cli/releases/download/v{resolved}/checksums.txt"
  format: "tar.gz"
  binary: "tkn"
```

**What each field does:**

| Field | Purpose |
|-------|---------|
| `adapter: cobra` | Use the Cobra `__complete` extractor (works for any Cobra-based CLI) |
| `versions` | Which minor versions to maintain catalogs for |
| `obtain.version_url` | URL to fetch to resolve the patch version (optional) |
| `obtain.version_match` | Regex with one capture group — the capture is `{resolved}` |
| `obtain.artifact_url` | Download URL with `{version}` and/or `{resolved}` tokens |
| `obtain.checksum_url` | SHA-256 checksum file — verified before the binary runs |
| `obtain.format` | `raw`, `tar.gz`, or `zip` |
| `obtain.binary` | Binary name (`raw`) or archive member path |

---

## Step 2: Test the registration locally

With `tkn` in your PATH (or downloaded to a temp dir):

```bash
# Refresh schemas for the changed registration
python -m extractor.refresh --base HEAD --head WORKTREE

# Or extract a single version directly (binary must be in PATH)
python -m extractor tkn 0.45

# Verify the output
cat schemas/tkn/0.45.json | python -m json.tool | head -20
```

Expected output shows `"name": "tkn"`, `"version": "0.45"`, and a non-empty `"subcommands"` list.

---

## Step 3: Confirm the schema loads in the server

```bash
# Start the server
cli-schema-mcp

# In another terminal
curl -s http://localhost:5001/health
# {"status": "healthy"}
```

Call `list_supported` via an MCP client to confirm `tkn` appears in the registry.

---

## Step 4: Open a Pull Request

```bash
git checkout -b feat/add-tkn
git add clis/tkn.yaml
git commit -m "feat: add tkn CLI registration (0.45, 0.46)"
git push origin feat/add-tkn
```

When the PR is opened against `main`, CI runs `extract-schemas.yml`:

1. Detects `clis/tkn.yaml` as changed
2. Downloads `tkn 0.45.x` and `tkn 0.46.x` from GitHub releases
3. Verifies SHA-256 checksums
4. Runs the Cobra extractor on each binary
5. Commits `schemas/tkn/0.45.json` and `schemas/tkn/0.46.json` to the branch automatically

The maintainer reviews the PR and the schema diff — no manual extraction step.

---

## What You Just Learned

1. **Registration** — one YAML file in `clis/` is all that's needed.
2. **Obtain block** — tells CI how to download, verify, and unpack the binary.
3. **CI handles extraction** — you never run the extractor manually in production.
4. **Zero Python changes** — adding a CLI is a configuration-only contribution.

## What's Next

| Topic | Link |
|-------|-------|
| Full obtain block field reference | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Architecture and schema registry | [Architecture](architecture.md) |
| How the extractor works | [Development Guide](development.md) |
| Deploying the server | [Deployment](deployment.md) |
| CI workflows | [CI/CD](ci-cd.md) |
