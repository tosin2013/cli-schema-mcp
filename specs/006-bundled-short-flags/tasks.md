---
description: "Task list for 006: validate_command accepts bundled short flags"
---

# Tasks: validate_command accepts bundled short flags

**Input**: `specs/006-bundled-short-flags/` (spec.md, plan.md)

**Tests**: Yes. Unit tests in `tests/test_tools.py`, using the existing `_patched` helper with a
sample schema that defines shorthands `-i` and `-t`.

## Phase 1: User Story 1 - bundled known shorthands validate (P1)

- [ ] T001 [US1] Add tests in `tests/test_tools.py`: `-it` and `-ti` validate as `valid: true`
  with no errors; `-it --bogus` gives exactly one error naming `--bogus`
- [ ] T002 [US1] In `cli_schema_mcp/src/tools/validate_command_tool.py`, accept a single-dash
  token longer than two characters when every letter is a known single-letter shorthand of the
  matched subcommand (FR-001, FR-002); a token that is itself a defined flag is never split

## Phase 2: User Story 2 - unknown letters are still caught (P1)

- [ ] T003 [US2] Add tests in `tests/test_tools.py`: `-iZ` gives exactly one error containing
  `-iZ` and `-Z`; `-iZQ` gives one error naming `-Z` and `-Q`
- [ ] T004 [US2] In `cli_schema_mcp/src/tools/validate_command_tool.py`, report one error per
  bundle with unknown letters, naming the original token and each unknown letter (FR-003)

## Phase 3: Polish

- [ ] T005 Run the full test suite (`python -m pytest`) and confirm every existing test still
  passes (FR-004)
