# Implementation Plan: validate_command accepts bundled short flags

**Branch**: `fix/006-bundled-short-flags` | **Date**: 2026-11-17 | **Spec**: [spec.md](spec.md)

## Summary

`validate_command` compares each flag token with the matched subcommand's flag names and
shorthands. A bundled token like `-it` matches neither. After a token fails the exact match,
check whether it is a single-dash bundle whose letters are all known shorthands; if so it is
valid, otherwise report one error naming the unknown letters.

## Technical Context

**Language/Version**: Python 3.12+ (C-01)
**Primary Dependencies**: none new
**Testing**: pytest (`tests/test_tools.py`, the existing `_patched(SAMPLE_SCHEMA)` helper)
**Constraints**: binary-free (C-02); structured response shape unchanged (C-04)

## Constitution Check

- C-02 binary-free: the change reads the schema only. ✅
- C-04 typed responses: same keys; error strings stay a list of str. ✅
- C-05 model-agnostic: no model-specific logic. ✅

## Design

- Keep `_parse_flags_from_string` as is (it returns tokens like `-it`).
- In `validate_command`, build `short = {shorthand letters}` from the node's flags.
- For each used flag not in `valid_flag_names`:
  - if it starts with a single `-`, has length > 2, and is not `--…`: compute the letters not in
    `short`. None → valid (no error). Some → one error:
    `"<token> is not a valid flag for '<context>' in version <v> (unknown: -Z, -Q)"`.
  - otherwise: the existing error.

## Project Structure

```text
cli_schema_mcp/src/tools/validate_command_tool.py   # change
tests/test_tools.py                                 # new tests
```
