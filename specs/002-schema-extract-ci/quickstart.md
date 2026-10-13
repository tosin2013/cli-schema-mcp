# Quickstart: Schema Extraction on Contribution

Validate the refresh behavior locally before relying on the workflow. Field names and exit codes are defined in [data-model.md](data-model.md) and [contracts/check-result.md](contracts/check-result.md).

## Prerequisites

- Repository checkout with `clis/` and `schemas/`
- Python 3.12 environment with the project installed (`uv pip install -e ".[dev]"`)
- Network access to the URL in the registration under test

## 1. Registration shape

Confirm a registration under `clis/` includes one `obtain` block that validates against [contracts/registration.schema.json](contracts/registration.schema.json).

Expected: `artifact_url`, `checksum_url`, `format`, and `binary` are present. `{version}` or `{resolved}` appears in the URLs. If `version_url` is set, `version_match` has one capture group.

## 2. Refresh one changed registration

From a clean worktree, change only one registration (for example, add a declared version or edit its obtain URL). Run:

```text
python -m extractor.refresh --base HEAD --head WORKTREE
```

Expected:

- Exit 0
- `schemas/<tool>/<version>.json` exists for every version that registration declares
- Each file’s `version` equals the declared version and its command list is non-empty
- Catalog files for registrations you did not edit are byte-identical to the base

## 3. Checksum failure

Point `checksum_url` at a file whose digest does not match the artifact. Re-run the command in step 2.

Expected:

- Exit 1
- stdout contains `FAIL`, the tool name, and the declared version
- `schemas/` is unchanged

## 4. Removal

Remove one declared version from the registration and re-run.

Expected: that version’s catalog file is gone, and the versions still declared remain.

Delete the registration file and re-run.

Expected: `schemas/<tool>/` is gone.

## 5. Contributor who cannot update the branch

Run the same refresh with the fork flag the workflow uses for a fork pull request (see [contracts/check-result.md](contracts/check-result.md)).

Expected:

- Exit 2 when the fresh catalogs differ
- The differing paths are listed
- No commit is created
