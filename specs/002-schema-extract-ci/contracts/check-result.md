# Check result

The refresh job is the reviewer-facing contract. It does not add an MCP tool.

## Invocation

The workflow runs when registration files change. Locally, the same entry point is:

```text
python -m extractor.refresh --base <revision> --head <revision>
```

`--base` and `--head` are the two trees to compare. The command reads `clis/` and writes `schemas/` only after every selected version succeeds.

## Exit codes

| Exit | Meaning |
|------|---------|
| 0 | Every changed registration succeeded. Catalogs were published, or they already matched and nothing was committed. |
| 1 | A named tool and declared version failed (obtain instruction, download, checksum, unpack, empty catalog, or extractor error). `schemas/` is unchanged. |
| 2 | The fresh catalogs differ and this run must not update the branch. stdout lists each differing path. |

## stdout

On success with changes: one line per published or retired path, then a line `published`.

On success with no changes: `catalogs already match`.

On exit 1: `FAIL <tool> <declared-version> <reason>`. No other version of that change is described as published.

On exit 2: one path per line under `catalogs differ:`, then `not updated`.

## Push rule

A same-repository branch that this job can update may commit the published `schemas/` paths and push that commit. A fork pull request must use exit 2 instead of pushing. The commit contains catalog files only.

## Timeout

The job fails at 90 minutes. That failure does not publish a partial catalog.
