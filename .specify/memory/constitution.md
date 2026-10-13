# cli-schema-mcp Constitution

## Core Principles

### I. Schema Accuracy First
Version-pinned schemas are the sole source of truth for flag validity. A hallucinated flag returned
by any tool is a defect. Every tool response must reflect what is actually present in the declared
version's pre-extracted schema JSON. The extractor, not the LLM, determines what is valid.

### II. Binary-Free at Runtime
The MCP server operates without any CLI binary present at query time. All schemas are pre-extracted
at build time and served as static JSON. The only exception: `detect_version` may invoke a local
binary when explicitly available in the calling environment. Remote AI services (Lightspeed, SaaS)
must work with no binary access whatsoever.

### III. Config-Driven Extensibility
Adding a new CLI requires only a `clis/<name>.yaml` file. Zero Python code changes to the server or
extractor. The YAML adapter type, version list, and version-parse pattern are the only per-CLI
decisions. CI handles extraction and schema publication automatically from the YAML declaration.

### IV. MCP-Native, Typed Responses
All tools are FastMCP tool functions returning `Dict[str, Any]` with a `status` field
(`"success"` or `"error"`). Responses carry typed, structured data — name, type, shorthand,
default, deprecated. Raw `--help` text is never returned for an LLM to re-parse; that would
simply move the hallucination problem one step downstream.

### V. Model-Agnostic Grounding
Schema validation fires as an MCP tool call before the model generates a command. The server MUST
work identically regardless of the underlying LLM (IBM Granite, Llama, Claude, GPT-4o). No
model-specific prompt engineering, no model-specific output parsing. The constraint is structural,
not probabilistic.

## Architecture Constraints

- MCP server: Python 3.12+ with FastMCP (template-mcp-server stack)
- Schema extractor: Python 3.10+, same repo but separate package (`extractor/`)
- CLI configs: YAML in `clis/` directory; one file per CLI tool
- No runtime binary dependencies on the server process
- Air-gapped deployment MUST be supported via OCI artifact distribution of the schema registry
- Schema JSON files are committed to the repo as generated artifacts (`schemas/<tool>/<version>.json`)
  and are NEVER hand-edited
- 80% test coverage minimum, enforced in CI

## Contribution Standards

- Each MCP tool lives in exactly one file under `src/tools/`
- Every tool docstring MUST include the structured metadata block:
  `TOOL_NAME`, `DISPLAY_NAME`, `USECASE`, `INSTRUCTIONS`, `INPUT_DESCRIPTION`,
  `OUTPUT_DESCRIPTION`, `EXAMPLES`, `PREREQUISITES`, `RELATED_TOOLS`
- Tools always return `Dict[str, Any]` and MUST NEVER raise — catch all exceptions and return
  `{"status": "error", "error": str(e), "message": "..."}`
- New CLIs are added via PR with only a `clis/<name>.yaml` config
- CI MUST validate the YAML schema and run an extraction smoke test on every CLI config PR
- CLI YAML configs are the primary contribution surface; code contributions are secondary
- Any CLI with a public binary and `--help` output is a valid contribution candidate
- Maintainers review for flag accuracy, not just YAML validity
- Community contributors are listed in `MAINTAINERS.md` per-CLI section

## Governance

This constitution supersedes all other implementation decisions. Amendments require a version bump:

- **MAJOR**: a principle is removed or fundamentally redefined
- **MINOR**: a new principle or section is added
- **PATCH**: clarification, wording, or typo fix

All PRs must verify compliance with these principles before merge. Complexity must be justified;
use `[COMPLEXITY_JUSTIFICATION]` comments when a violation is necessary and intentional.

**Version**: 1.0.0 | **Ratified**: 2026-10-12 | **Last Amended**: 2026-10-12
