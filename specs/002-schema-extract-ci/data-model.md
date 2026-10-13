# Data Model: Schema Extraction on Contribution

## CLI registration

One file, `clis/<name>.yaml`. Existing fields from feature 001 stay (`name`, `binary`, `adapter`, `versions`, `version_command`, `version_parse`). This feature adds one `obtain` object.

| Field | Required | Meaning |
|-------|----------|---------|
| `obtain.artifact_url` | yes | Download URL. `{version}` is the declared version. `{resolved}` is the capture below, or `{version}` when no pointer is set. |
| `obtain.checksum_url` | yes | SHA-256 source. Same token replacement as `artifact_url`. |
| `obtain.format` | yes | `raw`, `tar.gz`, or `zip`. |
| `obtain.binary` | yes | Filename to install (`raw`) or archive member path. |
| `obtain.version_url` | no | Fetched after `{version}` replacement. Its body is searched for the resolved token. |
| `obtain.version_match` | required when `version_url` is set | Regular expression. `{version}` is filled in before the match. The first capture group is `{resolved}`. |

`versions` remains the catalog identity. It is not replaced by the resolved patch tag.

Validation:

- `artifact_url` and `checksum_url` contain `{version}` or `{resolved}`.
- An instruction with neither token fails the registration before any download.
- `version_match` must contain one capture group.
- `format` outside the three values fails the registration.
- A registration with no `obtain` block fails the check. There is no fetch table keyed by CLI name.

Relationships:

- One registration has many declared versions.
- Each declared version has one flag catalog and, while the check runs, one downloaded program.
- The program is discarded after extraction. It is not a stored entity.

## Flag catalog

Unchanged from feature 001: `schemas/<tool>/<declared-version>.json`.

Required for this feature’s check:

- `version` equals the declared version.
- `subcommands` is a non-empty list, or the top-level node has commands the extractor recorded as subcommands.
- A catalog with no commands fails that version.

State of a catalog file during a check:

1. **Unchanged** — the registration file was not in the change set. The file must not be rewritten.
2. **Pending** — extraction succeeded in the temporary directory and is not yet copied.
3. **Published** — every changed registration succeeded, and the file was copied into `schemas/`.
4. **Retired** — the declared version or the whole registration was removed, and the file or directory was deleted in the same publish step as the successful refreshes.

A failed version leaves the previous published files in place.

## Check result

Not stored as a project file. It is the job outcome the reviewer reads.

| Outcome | When | What the reviewer sees |
|---------|------|------------------------|
| Pass, catalogs saved | Every changed version succeeded, the actor can update the branch, and at least one catalog file changed | A commit containing only those catalog updates |
| Pass, no commit | Every changed version succeeded and the catalogs already match | A statement that the catalogs already match |
| Fail, difference report | The actor cannot update the branch and the fresh catalogs differ | The catalog paths that differ, then a non-zero exit |
| Fail, named version | Download, checksum, unpack, match, or extraction failed | The tool name, the declared version, and the reason. No catalog for that version is published |

## Change set

Derived from the registration files that differ from the base revision. Not a file the maintainer edits.

| Change | Refresh | Delete |
|--------|---------|--------|
| File added | Every declared version | Nothing |
| File modified | Every version still declared | Versions that were declared in the base file and are not declared now |
| File deleted | Nothing | `schemas/<tool>/` |

Registrations outside the change set have no transition.
