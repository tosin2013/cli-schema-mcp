# Contributing to cli-schema-mcp

Thank you for your interest in contributing! This guide explains how to contribute to this project.
The primary contribution surface is **adding new CLI schemas** via a YAML config file — no Python
code required for Cobra-based CLIs.

## Table of Contents

- [Adding a New CLI (primary contribution)](#adding-a-new-cli-primary-contribution)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Commit Conventions](#commit-conventions)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)
- [Coding Standards](#coding-standards)
- [Adding New MCP Tools](#adding-new-mcp-tools)
- [Testing Requirements](#testing-requirements)
- [Getting Help](#getting-help)

## Adding a New CLI (primary contribution)

Adding a CLI to the schema registry requires **only a YAML config file** — no Python code changes
for Cobra-based CLIs.

### Step 1: Open an issue

Use the [New CLI Schema Request](.github/ISSUE_TEMPLATE/new-cli-request.yml) issue template to
describe the CLI and confirm CI binary availability.

### Step 2: Create `clis/<name>.yaml`

```yaml
name: tkn
display_name: "Tekton CLI"
description: "CLI for Tekton Pipelines"
binary: tkn
adapter: cobra            # cobra | help-parser | custom
versions:
  - "0.37"
  - "0.38"
  - "0.39"
version_command: "tkn version"
version_parse: "Client version: {version}"
upstream_repo: "https://github.com/tektoncd/cli"
maintainers:
  - "your-github-username"
```

#### YAML field reference

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Binary name (used as schema directory name) |
| `display_name` | No | Human-readable name |
| `description` | No | One-line description |
| `binary` | Yes | The actual binary name in PATH |
| `adapter` | Yes | `cobra`, `help-parser`, or `custom` |
| `versions` | Yes | List of version strings to extract |
| `version_command` | Yes | Shell command to print the version |
| `version_parse` | Yes | Regex or `{version}` template to extract semver from output |
| `upstream_repo` | No | GitHub URL of the CLI project |
| `maintainers` | No | GitHub usernames of schema maintainers |
| `help_flag` | help-parser only | Flag to show help (default: `--help`) |
| `flag_regex` | help-parser only | Regex to parse flag lines from `--help` output |
| `subcommand_regex` | help-parser only | Regex to parse subcommand lines |
| `extraction_script` | custom only | Path to custom extraction script |
| `obtain` | Yes | Download instruction block — see below |

#### The `obtain` block (required)

Every registration must include exactly one `obtain` block. CI uses it to download, verify,
and run the CLI binary without any hand-extracted binary or per-CLI code.

```yaml
obtain:
  artifact_url: "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-{version}/openshift-client-linux.tar.gz"
  checksum_url: "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-{version}/sha256sum.txt"
  format: "tar.gz"
  binary: "oc"
```

| Field | Required | Description |
|---|---|---|
| `artifact_url` | Yes | Download URL. Must contain `{version}` or `{resolved}`. |
| `checksum_url` | Yes (unless `skip_checksum: true`) | URL of the SHA-256 checksum. Same tokens as `artifact_url`. |
| `format` | Yes | Archive format: `raw`, `tar.gz`, or `zip`. |
| `binary` | Yes | Installed filename for `raw`, or archive member path otherwise. |
| `version_url` | No | URL to fetch for the resolved patch tag (fill `{version}` first). |
| `version_match` | Required with `version_url` | Regex with one capture group for `{resolved}`. |
| `skip_checksum` | No (default: `false`) | Set `true` only when the upstream project publishes no checksum file. Reduces supply-chain security — requires maintainer review. |

**Token substitution**: `{version}` is replaced with the declared version string (e.g. `4.22`).
`{resolved}` is replaced with the first capture group from `version_match`, or equals `{version}`
when `version_url` is omitted.

**Checksum**: The file at `checksum_url` must be a bare 64-hex SHA-256 digest, or a `sha256sum`
listing. The artifact is not unpacked or executed unless the digest matches. Use
`skip_checksum: true` only for CLIs whose upstream project does not publish a checksum file (e.g.
KubeVirt `virtctl`). This must be noted in the PR and reviewed by a maintainer.

**Example with version pointer** (kubectl):

```yaml
obtain:
  version_url: "https://dl.k8s.io/release/stable-{version}.txt"
  version_match: "v(\\d+\\.\\d+\\.\\d+)"
  artifact_url: "https://dl.k8s.io/release/{resolved}/bin/linux/amd64/kubectl"
  checksum_url: "https://dl.k8s.io/release/{resolved}/bin/linux/amd64/kubectl.sha256"
  format: "raw"
  binary: "kubectl"
```

#### Adapter selection

- **`cobra`**: Use for any CLI built with the Go [Cobra](https://github.com/spf13/cobra) framework
  (oc, kubectl, helm, tkn, argocd, operator-sdk, etc.). Extraction is fully automatic.
- **`help-parser`**: Use for CLIs that do not implement Cobra `__complete` (for example ansible-navigator). Podman does implement it and uses the `cobra` adapter.
  Requires `flag_regex` and `subcommand_regex` to be configured.
- **`custom`**: For CLIs with non-standard help formats. Point to a Python script via `extraction_script`.

### Step 3: Run the extractor locally

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run extraction (binary must be in PATH)
python -m extractor tkn 0.38

# Verify output
cat schemas/tkn/0.38.json | python -m json.tool | head -40
```

Compare the output against `tkn pipeline --help` to verify flag accuracy.

#### Schema size and the node cap

The cobra adapter limits extraction to **500 unique command paths** (`_MAX_NODES = 500`)
to keep schema JSON files under ~20 MB so they can be committed to git. This is plenty
for most CLIs but intentionally truncates very large command trees (helm has hundreds of
subcommands and sub-subcommands).

**What you get in the repo**: the most-commonly-used command paths, sufficient for
`validate_command`, `get_flags`, and `list_subcommands` on the main workflows.

**If you need deeper coverage** (all subcommands, including rarely-used ones), build the
schema yourself with a higher limit:

```bash
# Set a higher node limit for local use (do not commit files >50 MB to the repo)
python3 -c "
from extractor.adapters import cobra
cobra._MAX_NODES = 2000   # adjust as needed
from extractor.main import main
import sys; sys.argv = ['extractor', 'helm', '4.3']
main()
"
```

> **Warning for large CLIs (helm, argocd, operator-sdk):** schemas above ~50 MB cannot be
> committed to this repository (GitHub enforces a 100 MB hard limit; our pre-commit
> hooks will reject files over 50 MB as a safety margin). If you need a full schema for
> internal use, run the extractor locally in your own environment and serve it via
> `SCHEMA_REGISTRY_PATH` rather than committing it here.

### Step 4: Submit a PR

Include both the `clis/tkn.yaml` config and the extracted `schemas/tkn/*.json` files.
CI will validate the YAML schema, run an extraction smoke test, and check JSON integrity.

### What maintainers review

- Flag names match the actual binary output
- Flag types, shorthands, and defaults are correct
- All declared versions have extracted schema files
- YAML config is complete (all required fields present)
- Schema file size is under 50 MB per version (large CLIs: note the node cap above)

## Getting Started

1. **Fork the repository** on GitHub.

2. **Clone your fork:**
   ```bash
   git clone https://github.com/<your-username>/cli-schema-mcp.git
   cd cli-schema-mcp
   ```

3. **Set up the development environment:**
   ```bash
   make install
   ```
   This creates a virtual environment, installs all dependencies (including dev), and sets up pre-commit hooks.

4. **Verify everything works:**
   ```bash
   make test
   make pre-commit
   ```

## Development Workflow

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Make your changes** following the [Coding Standards](#coding-standards).

3. **Run quality checks locally:**
   ```bash
   make lint        # Check linting issues
   make format      # Auto-format code
   make test        # Run test suite
   make coverage    # Run tests with coverage report
   make pre-commit  # Run all pre-commit hooks
   ```

4. **Commit your changes** using [Conventional Commits](#commit-conventions).

5. **Push and open a Pull Request** against `main`.

## Commit Conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for clear history and automated release notes.

### Format

```
<type>(<optional scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `docs` | Documentation only changes |
| `style` | Code style (formatting, semicolons, etc.) |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `test` | Adding or correcting tests |
| `build` | Changes to build system or dependencies |
| `ci` | Changes to CI configuration |
| `chore` | Other changes that don't modify src or test files |

### Examples

```
feat(tools): add weather forecast tool
fix(oauth): handle expired token refresh correctly
docs: update deployment instructions for OpenShift
test(tools): add edge case tests for multiply tool
ci: add dependabot configuration
```

## Pull Request Process

1. **Fill out the PR template completely.** The template includes a checklist; all items must be addressed.

2. **Ensure all CI checks pass:**
   - Pre-commit hooks (linting, formatting, type checking)
   - Test suite with coverage >= 80%
   - Security scanning (Bandit)

3. **Link related issues** using keywords: `Closes #123`, `Fixes #456`.

4. **Keep PRs focused.** One logical change per PR. If you find unrelated issues, open separate PRs.

5. **Respond to review feedback** promptly. Push fixes as new commits (don't force-push during review).

6. **Squash and merge** is the default merge strategy. Your PR title becomes the changelog entry, so make it clear and descriptive.

## Issue Guidelines

### Before Opening an Issue

- Search existing issues to avoid duplicates.
- Check the README and documentation for answers.

### Bug Reports

Use the **Bug Report** template. Include:
- Steps to reproduce
- Expected vs. actual behavior
- Environment details (OS, Python version, etc.)
- Logs or error messages

### Feature Requests

Use the **Feature Request** template. Include:
- Problem statement (what you're trying to solve)
- Proposed solution
- Alternatives considered

### Labels

Issues are automatically labeled by type. You can also add:
- `good first issue` - suitable for newcomers
- `help wanted` - looking for contributors
- `priority/high` - needs attention soon

## Coding Standards

### Python Style

- **PEP 8** compliance (enforced by Ruff)
- **Line length**: 88 characters (Ruff default)
- **Imports**: sorted by isort (via Ruff)
- **Quotes**: double quotes

### Type Annotations

Required for all public functions and methods:
```python
async def my_tool(param: str, count: int = 1) -> Dict[str, Any]:
    ...
```

### Documentation

Google-style docstrings for all public APIs:
```python
async def my_tool(param: str) -> Dict[str, Any]:
    """Short description of the tool.

    Args:
        param: Description of the parameter.

    Returns:
        Dict[str, Any]: Description of the return value.

    Raises:
        ValueError: When param is invalid.
    """
```

### Error Handling

- Use structured logging (`structlog`) for all log messages.
- Return error dictionaries with `status`, `error`, and `message` keys.
- Never expose internal errors to clients.

## Adding New MCP Tools

1. **Create the tool module** in `template_mcp_server/src/tools/`:
   ```python
   # template_mcp_server/src/tools/your_tool.py
   from typing import Any, Dict
   from template_mcp_server.utils.pylogger import get_python_logger

   logger = get_python_logger()

   async def your_tool_function(param: str) -> Dict[str, Any]:
       """Your tool description."""
       try:
           # Implementation
           return {"status": "success", "result": "value"}
       except Exception as e:
           logger.error(f"Error in your tool: {e}")
           return {"status": "error", "error": str(e)}
   ```

2. **Register in MCP server** (`template_mcp_server/src/mcp.py`):
   ```python
   from template_mcp_server.src.tools.your_tool import your_tool_function

   def _register_mcp_tools(self) -> None:
       # ... existing registrations ...
       self.mcp.tool()(your_tool_function)
   ```

3. **Add tests** in `tests/`:
   ```python
   # tests/test_your_tool.py
   import pytest
   from template_mcp_server.src.tools.your_tool import your_tool_function

   @pytest.mark.asyncio
   async def test_your_tool_success():
       result = await your_tool_function("test")
       assert result["status"] == "success"
   ```

4. **Update documentation** in `README.md` and `template_mcp_server/src/tools/README.md`.

## Testing Requirements

- All new code must have corresponding tests.
- Minimum **80% code coverage** is required.
- Tests must pass on Python 3.12 and 3.13.
- Use `pytest` with `pytest-asyncio` for async tests.
- Mock external dependencies; do not make real network calls in tests.

### Running Tests

```bash
make test              # Run all tests
make coverage          # Run with coverage report
pytest tests/ -v       # Verbose output
pytest tests/ -k name  # Run specific test by name
```

## Getting Help

- **Issues**: Open an issue for bugs or feature requests.
- **Discussions**: Use GitHub Discussions for questions and ideas.
- **Documentation**: Check the README and in-code documentation.

Thank you for contributing!
