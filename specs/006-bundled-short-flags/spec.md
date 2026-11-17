# Feature Specification: validate_command accepts bundled short flags

**Feature Branch**: `fix/006-bundled-short-flags`

**Created**: 2026-11-17

**Status**: Draft

**Input**: Roadmap entry 006. `validate_command` reports `podman run -it fedora bash` as invalid
("`-it` is not a valid flag") although the podman schema defines both `-i` (`--interactive`)
and `-t` (`--tty`). Bundled short flags are common (`-it`, `-xzf`, `-ef`), so agents that trust
the tool rewrite correct commands.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A correct command with bundled short flags validates (Priority: P1)

As an AI agent that validates a command before running it, I want `podman run -it fedora bash`
to be reported valid, so that I don't rewrite a correct command into a worse one.

**Why this priority**: This is the whole item. A false "invalid" on a correct command is the
opposite of what the tool is for.

**Independent Test**: Call `validate_command("podman", "5.4", "podman run -it fedora bash")`
and check `valid` is `true` and `errors` is empty.

**Acceptance Scenarios**:

1. **Given** a subcommand whose schema defines the shorthands `-i` and `-t`, **When** the
   command contains the token `-it`, **Then** the result is `valid: true` with no errors.
2. **Given** the same subcommand, **When** the token is `-ti`, **Then** the result is the same
   as for `-it` (letter order doesn't matter).
3. **Given** a subcommand with shorthands `-i` and `-t`, **When** the command contains `-it`
   and also a separate unknown long flag `--bogus`, **Then** the result is `valid: false` with
   exactly one error, naming `--bogus`.

---

### User Story 2 - A bundle with an unknown letter is still caught (Priority: P1)

As an agent, I want a bundle with a letter the subcommand doesn't define to stay invalid, and
to be told which letter, so that I can fix just that part.

**Why this priority**: Accepting bundles must not open a hole for hallucinated flags.

**Independent Test**: Call `validate_command("podman", "5.4", "podman run -iZ fedora bash")`,
where `-Z` isn't a shorthand of `podman run`, and check `valid` is `false`.

**Acceptance Scenarios**:

1. **Given** a subcommand with shorthand `-i` but no `-Z`, **When** the command contains
   `-iZ`, **Then** the result is `valid: false` with exactly one error, and that error contains
   both the original token `-iZ` and the unknown letter `-Z`.
2. **Given** a bundle where several letters are unknown (for example `-iZQ`), **When** it is
   validated, **Then** there is still exactly one error for that token, and it names every
   unknown letter (`-Z` and `-Q`).

---

### Edge Cases

- A single-dash token that is itself a defined flag name or shorthand (for example a CLI that
  defines `-version` as a flag) is accepted as that flag and never split.
- A two-character token such as `-i` is a plain shorthand, not a bundle; it is checked as today.
- Long flags (`--tty`), `--flag=value`, the bare `-`, and everything after `--` behave exactly
  as today.
- A bundle is only expanded when every letter is a single-letter shorthand of the matched
  subcommand. Attached values (`-p8080`, `-ojson`) are out of scope: they are reported invalid
  as today.
- The rest of the response (`status`, `tool`, `version`, `matched_version`, `command_string`,
  `subcommand_context`, `message`) keeps its current shape and meaning (C-04).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A single-dash token longer than two characters that is not itself a defined flag
  name or shorthand MUST be treated as a bundle of single-letter shorthands.
- **FR-002**: A bundle MUST be valid when every letter is a shorthand defined for the matched
  subcommand.
- **FR-003**: A bundle with one or more unknown letters MUST produce exactly one error. The
  error MUST contain the original token and each unknown letter written as `-<letter>`.
- **FR-004**: All other validation behaviour MUST stay unchanged; the existing tests in
  `tests/test_tools.py` MUST keep passing.
- **FR-005**: The tool MUST stay binary-free and model-agnostic (C-02, C-05): only the schema is
  used.

### Key Entities

- **Bundle**: a token such as `-it` standing for several single-letter shorthands (`-i -t`).

## Allowed paths

- `cli_schema_mcp/src/tools/validate_command_tool.py`
- `tests/test_tools.py`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `podman run -it fedora bash` validates as `valid: true` for every podman schema
  version in the registry (5.2, 5.3, 5.4).
- **SC-002**: 100% of bundles containing an unknown letter are reported invalid, naming the
  unknown letters.
- **SC-003**: The full existing test suite passes unchanged, with coverage still at or above 80%.

## Assumptions

- Shorthands in the schema are stored as `-<letter>` (for example `"shorthand": "-i"`), as in
  every schema in `schemas/` today.
- Only the matched subcommand's flags are used. Inherited global flags are already merged into
  each node by the extractor.
