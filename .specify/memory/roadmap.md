<!--
SYNC IMPACT REPORT
==================
Version change: 1.2.3 → 1.2.4
Bump rationale: PATCH — registry destination decided for entry 003 (quay.io/takinosh/cli-schema-mcp);
workflow updated from GHCR to quay.io. Entry 002 verified (previous revision).
Version change: 1.2.3 → 1.2.4 (this revision)

Prior bump rationale (1.2.2 → 1.2.3): entry 002 status transition (implemented → verified) after
GitHub Actions successfully ran extract-schemas.yml on a clis/ change, downloaded and
verified tkn 0.45/0.46 binaries, and committed schemas/tkn/0.45.json and
schemas/tkn/0.46.json to main. Also records cobra adapter fix (seen-set).

Changes this revision:
  - Entry 002 status: implemented → verified
  - Entry 002 notes updated with verification date and tkn registration as proof
  - cobra adapter fix noted (branch_seen → shared seen prevents exponential blowup)

Prior SYNC IMPACT REPORT (1.2.1 → 1.2.2):

Prior SYNC IMPACT REPORT (1.2.0 → 1.2.1):
  - Q1 resolved: help-parser stays for CLIs without __complete; podman uses cobra adapter
  - Q2 resolved: ENABLE_AUTH code default is False
  - C-06 annotated so the code default matches .env.example
  - Specs affected: none (001 follow-up only)

Specs affected: 002 (status + description amended)
Open questions added/resolved: none
-->

# cli-schema-mcp — Spec Roadmap

Living, non-binding map of the specs planned for cli-schema-mcp. It captures the spec-specific
discussion, decisions, technology choices, outcomes, and constraints surfaced during the
constitution and planning phases so they are not lost before the specs that need them are written.
Foundations: the project [constitution](constitution.md).

Status legend (lifecycle): **undecided** · **needs-info** · **planned** · **specced** ·
**in-progress** · **implemented** · **verified** · **deferred** · **abandoned**.

---

## Vision & End States

- **Community standard**: A vendor-neutral, community-maintained open source registry of
  versioned CLI flag schemas — usable by any AI tool (Claude Code, GitHub Copilot, OpenShift
  Lightspeed, custom agents) regardless of the underlying LLM.
- **Red Hat portfolio integration**: cli-schema-mcp ships as a companion MCP server to the
  Lightspeed portfolio (RHEL Lightspeed, OpenShift Lightspeed, Ansible Lightspeed), providing
  the version-pinned schema grounding layer that grounds autonomous CLI command generation.
- **Zero hallucination for supported tools**: When the schema server is active, `validate_command`
  rejects 100% of flag hallucinations for supported CLI tools and versions. The AI never gets a
  chance to suggest a flag that is not in the schema.
- **Air-gapped enterprise deployability**: Schemas ship as OCI artifacts. Open-weight models
  running in isolated clusters (where frontier model APIs are unavailable) can rely on a
  pre-built, offline schema registry.
- **Frictionless community contribution**: Adding a new CLI requires only a YAML config file.
  Any maintainer of any Cobra-based CLI can register it in under 30 minutes with no Python code
  changes.

Both tracks — Red Hat portfolio integration and open source community adoption — are pursued in
parallel with equal weight.

---

## Constraints & Decisions

- **C-01 — Python / FastMCP stack**: Server implemented in Python 3.12+ with FastMCP, matching
  the template-mcp-server baseline. The PRD originally specified TypeScript; this was overridden
  to align with the Red Hat template ecosystem and simplify a single-language codebase.

- **C-02 — Binary-free at runtime**: The MCP server MUST operate without any CLI binary present
  at query time. Schemas are pre-extracted at build time and served as static JSON. This is the
  architecture that enables remote AI services (Lightspeed backend, SaaS) to use the server
  without binary access.

- **C-03 — Config-driven extensibility**: A new CLI is added via a single `clis/<name>.yaml`
  file. Zero Python code changes to the server or extractor. If adding a CLI requires code
  changes, the principle is violated.

- **C-04 — MCP-native typed responses**: Tools MUST return structured `Dict[str, Any]` with
  typed flag fields. Raw `--help` text is never returned for the LLM to re-parse — that moves
  the hallucination problem downstream rather than eliminating it.

- **C-05 — Model-agnostic grounding**: No model-specific logic anywhere in the server. The
  schema constraint fires as an MCP tool call before generation; works identically with Granite,
  Llama, Claude, GPT-4o, or any future model.

- **C-06 — Auth disabled by default**: Schema data is not sensitive. `ENABLE_AUTH=False` in
  `.env.example` and as the `cli_schema_mcp` settings code default (set 2026-10-12; the inherited
  template default of `True` is not used by this server). Auth infrastructure inherited from the
  template is available but off unless `ENABLE_AUTH=True`.

- **C-07 — OCI publishing is Phase 3**: Schemas in Phase 1 are committed as JSON files to the
  repository and served from the local filesystem. OCI artifact publishing is a deliberate Phase 3
  deliverable, not a Phase 1 requirement.

- **C-08 — Parallel end-state tracks**: Red Hat portfolio integration and open source community
  adoption are pursued simultaneously. Neither is subordinate to the other. Community PRs and
  internal Lightspeed conversations proceed in parallel.

---

## Planned Specs

### Core Platform

### 001 — Core MCP Server & Schema Registry  [status: verified]

- **Description:** The foundational FastMCP server exposing five tools (`get_flags`,
  `list_subcommands`, `validate_command`, `detect_version`, `list_supported`), backed by a
  versioned schema registry of pre-extracted CLI flag JSON files. Includes the Python extractor
  package with Cobra, help-parser, and custom adapters, and four initial CLI configs (oc, kubectl,
  kustomize, podman).
- **Outcome:** A running MCP server that returns version-pinned flag schemas for ≥4 CLIs,
  rejects hallucinated flags via `validate_command`, and passes 80% test coverage in CI.
- **Scope (in):** Five MCP tools; schema_registry module; extractor package with cobra
  (`__complete` primary, help-text fallback), help-parser, and custom adapters; `clis/` YAML
  config model; `schemas/` registry; 4 initial CLIs (oc 4.18–4.22, kubectl 1.31–1.35,
  kustomize 5.3–5.5, podman 5.2–5.4); test suite ≥80% coverage.
- **Scope (out):** OCI publishing (spec 003 owns proof of the publish workflow); Lightspeed
  integration; community CNCF CLIs; InstructLab dataset; CI auto-extraction pipeline proof
  (spec 002). Workflow files `.github/workflows/extract-schemas.yml` and
  `.github/workflows/publish-schemas-oci.yml` were authored while closing 001 tasks T005 and
  T013; execution and acceptance stay with 002 and 003.
- **Depends on:** none
- **Governed by:** C-01, C-02, C-03, C-04, C-05, C-06
- **Spec dir:** specs/001-cli-schema-mcp/
- **Notes:** ~~Code was built directly from spec without a plan.md. 13 convergence tasks remain
  (T001–T013): highest priority are T001 (fix broken test imports, unblocks 80% coverage gate),
  T002 (extractor __main__.py), T003 (path fragility at runtime), T006–T009 (missing schema
  extractions for all 4 CLIs). CI gate currently fails at 14.87% because inherited template
  tests import the old `template_mcp_server` package name.~~ Superseded 2026-10-12: T001–T013
  are done. Local pytest coverage was 84.15% (325 passed) against the 80% CI gate, and inherited
  tests import `cli_schema_mcp`. There is still no `plan.md`. Schema JSON for the four CLIs is
  in the working tree and still needs a git commit before a clone matches this outcome. Debrief:
  `specs/001-cli-schema-mcp/roadmap-reviews/debrief-2026-10-12T134911Z.md`.

### 002 — Schema Extraction CI Pipeline  [status: verified]

- **Description:** Generic, config-driven schema refresh pipeline: each `clis/<name>.yaml`
  registration carries one `obtain` block (artifact URL, checksum URL, archive format, member
  path, optional version pointer). `python -m extractor.refresh --base <rev> --head <rev>`
  detects changed registrations, downloads and SHA-256 verifies each declared version's binary,
  runs the extractor, and publishes `schemas/<tool>/<version>.json` only after every selected
  version succeeds (all-or-nothing). Fork pull requests receive exit 2 and a catalog diff list
  instead of a branch push.
- **Outcome:** Merging a new `clis/<name>.yaml` config (with an `obtain` block) automatically
  populates the schema registry without any manual extraction step. A registration change for a
  CLI this project has never fetched before produces its catalog without a code change.
- **Scope (in):** `extractor/obtain.py` (download, SHA-256, unpack raw/tar.gz/zip with up to
  3-layer unwrap); `extractor/refresh.py` (change detection, temp-dir all-or-nothing publish,
  exit 0/1/2, version retirement); `extractor/cli_config.py` extended with `ObtainConfig`;
  `obtain` block added to `clis/oc.yaml`, `clis/kubectl.yaml`, `clis/kustomize.yaml`,
  `clis/podman.yaml`; `.github/workflows/extract-schemas.yml` updated (90 min timeout,
  `python -m extractor.refresh`, fork-PR `--no-push` path); `CONTRIBUTING.md` obtain-block
  reference; pytest coverage of token fill, checksum, unpack, publish, no-push, and removal.
- **Scope (out):** OCI artifact publishing (spec 003); schema signing; schema diffing/changelog.
  ~~Binary installation steps per CLI; matrix strategy per CLI~~ (superseded: replaced by the
  generic obtain-block model, no per-CLI shell code required).
- **Depends on:** 001 (status: verified)
- **Governed by:** C-03, C-02
- **Spec dir:** specs/002-schema-extract-ci/
- **Notes:** Implemented 2026-10-13. Verified 2026-10-14. All 22 tasks [X]; 355 tests
  passing. C-02 boundary verified. GitHub Actions run `38559288553` detected `clis/tkn.yaml`
  as a new registration, downloaded tkn 0.45.2 and 0.46.1, verified SHA-256, extracted
  schemas, and committed `schemas/tkn/0.45.json` and `schemas/tkn/0.46.json` to main in 18s.
  Also fixed a cobra adapter bug: `branch_seen = seen | {key}` was replaced with
  `seen.add(key)` (shared mutable set) to prevent exponential blowup from revisiting nodes
  via the `help` subcommand recursion in large CLIs like helm.
  Debrief: `specs/002-schema-extract-ci/roadmap-reviews/debrief-2026-10-13T193652Z.md`.

### 003 — OCI Artifact Publishing  [status: implemented]

- **Description:** GitHub Actions release workflow that packages the `schemas/` directory as an
  OCI artifact and pushes it to a container registry (e.g. quay.io) on each tagged release.
  Enables air-gapped OCP clusters to pull the schema registry without internet access.
- **Outcome:** Air-gapped enterprise deployments can pull a version-tagged OCI artifact
  containing the complete schema registry and mount it into the server container. No internet
  access required at server runtime.
- **Scope (in):** `.github/workflows/publish-schemas-oci.yml`; OCI packaging of `schemas/`
  directory; quay.io push on `v*` tags; documentation for OCI pull usage in `Containerfile` and
  README; `SCHEMA_REGISTRY_PATH` env var to point at mounted OCI content.
- **Scope (out):** Schema signing / attestation; multi-registry push; schema versioning beyond
  directory structure.
- **Depends on:** 001, 002
- **Governed by:** C-02, C-07
- **Spec dir:** specs/003-oci-publishing/
- **Notes:** Implemented 2026-10-14. Registry: `quay.io/takinosh/cli-schema-mcp`. First
  release `v0.1.1` pushed successfully (layer digest sha256:35d09f9b…). Artifact is publicly
  pullable; `:latest` and versioned tags both live. README updated with `oras pull` example
  and `SCHEMA_REGISTRY_PATH` docs. Containerfile updated with commented OCI build alternative.
  Status advances to `verified` after a real air-gapped pull + MCP server start is observed
  in a disconnected environment.

### Integrations

### 004 — OpenShift / Lightspeed Integration  [status: needs-info]

- **Description:** Integration of cli-schema-mcp as a companion MCP server in the Red Hat
  Lightspeed portfolio — initially OpenShift Lightspeed (fixes the documented v1.1.3 version
  mismatch bug), then RHEL Lightspeed and Ansible Lightspeed.
- **Outcome:** _to be defined_ — depends on Lightspeed BU alignment conversation.
- **Scope (in):** _to be defined_
- **Scope (out):** Red Hat Developer Hub marketplace listing (separate effort); InstructLab
  dataset (spec 005).
- **Depends on:** 001, 002, 003
- **Notes:** Blocked on BU conversation — is CLI schema grounding on the Lightspeed roadmap?
  This question was intentionally deferred until the Phase 1 PoC demo exists and can be shown.
  Entry status will move to `planned` after the conversation. The documented OCP 4.18 docs
  served to 4.16/4.17 clusters bug in OpenShift Lightspeed v1.1.3 is the strongest concrete
  evidence of need. RHEL Lightspeed has no flag grounding at all today — highest-urgency gap.
  Ansible Lightspeed feeds into Event-Driven Ansible autonomous execution — second-highest risk.

### Community & Ecosystem

### 005 — Community CLI Registry & Ecosystem  [status: planned]

- **Description:** Open source community contribution model enabling CNCF and non-Red Hat CLI
  maintainers to add their tools to the schema registry. Includes community governance, CNCF CLI
  coverage (flux, crossplane, istioctl, etc.), InstructLab fine-tuning dataset publication, and
  conference presence (DevConf, Red Hat Summit).
- **Outcome:** ≥3 non-Red Hat CLIs contributed by external maintainers. InstructLab fine-tuning
  dataset published from versioned schemas. Community contribution model documented and self-sustaining.
- **Scope (in):** `CONTRIBUTING.md` expansion (already started); `MAINTAINERS.md`; community
  CNCF CLI YAML configs; `.github/ISSUE_TEMPLATE/new-cli-request.yml` (already done); InstructLab
  dataset export script; conference talk submission.
- **Scope (out):** Red Hat portfolio integration (spec 004); OCI publishing (spec 003).
- **Depends on:** 001, 002
- **Notes:** Contribution infrastructure (CONTRIBUTING.md, MAINTAINERS.md, issue template) was
  built in the 001 implementation pass. The missing piece is actual community outreach — blog post
  on developers.redhat.com, GitHub topic tags, initial CNCF CLI configs as examples for
  contributors. InstructLab dataset format TBD pending conversation with InstructLab team.

---

## Open Questions

- **Q1 — Extractor parsing ceiling**: ~~At what CLI count or failure rate does `--help` regex
  parsing become insufficient, and should a structured Cobra extraction mechanism
  (GenMarkdownTree side-car Go tool, machine-readable `__complete` metadata output) be
  investigated to replace or augment it?~~ ~~Amended 2026-10-12: wait until ≥10 CLIs and ask
  whether help-parser CLIs need the same treatment.~~ Resolved 2026-10-12: do not wait for 10
  CLIs and do not add another extractor. A CLI that implements `__complete` uses the cobra
  adapter. Podman moved from help-parser to cobra; re-extracted 5.2/5.3/5.4 schemas include
  `healthcheck` and `run --hostname`. `auto-update` is present on 5.4 and absent from 5.2 and
  5.3 completion output. Help-parser remains for CLIs with no structured completion. Open a new
  spec only when that regex path drops or mis-types a flag name, type, or default.

- **Q2 — ENABLE_AUTH code default**: ~~C-06 is met by `.env.example` (`ENABLE_AUTH=False`).
  `settings.py` still defaults `ENABLE_AUTH` to `True` (inherited template behavior). Whether
  to flip the code default is undecided. Do not change template OAuth plumbing until that
  decision is made. Not a blocker for entry 001 `verified`.~~ Resolved 2026-10-12: the
  `cli_schema_mcp` code default is `False`, matching `.env.example` and C-06. The unused
  `template_mcp_server` copy was left unchanged.

- The Lightspeed roadmap alignment question was intentionally deferred until the Phase 1 PoC
  demo exists. Revisit after 001 reaches `verified` status. 001 reached `verified` on
  2026-10-12, so this question is now due. Entry 004 stays `needs-info` until that conversation
  happens.

---

## Cross-Cutting Notes

- **Repo transfer path**: Phase 1 lives at `github.com/tosin2013/cli-schema-mcp`. Red Hat
  adoption (if achieved) moves it to `github.com/RedHatOfficial/cli-schema-mcp` or merges into
  `openshift/openshift-mcp-server`. Neither is assumed — the PoC must earn it.
- **Extractor is build-time only**: The `extractor/` package is never imported by the MCP server
  runtime. This separation is intentional and must be preserved across all specs. Any spec that
  blurs this boundary violates C-02. Verified 2026-10-13: `extractor/obtain.py` and
  `extractor/refresh.py` (added by spec 002) are absent from `cli_schema_mcp/`.
- **Template inheritance debt**: The codebase inherits OAuth, storage, and other template
  infrastructure that is not part of the cli-schema-mcp feature set. ~~Test files for those modules
  still reference `template_mcp_server` (convergence finding F1/T001).~~ Superseded 2026-10-12:
  those tests now import `cli_schema_mcp` (T001). Future specs should treat this infrastructure
  as background plumbing — neither extend nor remove it without a deliberate decision. See Q2.

---

**Version**: 1.2.5 | **Ratified**: 2026-10-12 | **Last Amended**: 2026-10-14
