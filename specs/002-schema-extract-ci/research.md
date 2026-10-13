# Research: Schema Extraction on Contribution

## 1. Registration-only obtain instruction

- **Decision**: Each `clis/<name>.yaml` gains one `obtain` block. The refresh job downloads and unpacks from that block only. The per-CLI functions in `scripts/extract-all-schemas.sh` (`fetch_oc`, `fetch_kubectl`, `fetch_kustomize`, `fetch_podman`) are not used by the check and are not a fallback.
- **Rationale**: The spec requires a CLI this project has never fetched to refresh from its registration alone. The current script branches on CLI name, so a new registration fails until someone edits that script.
- **Alternatives considered**: Keep the hardcoded fetchers for the four current CLIs and require code for any new one. Rejected because the spec forbids a built-in fetch fallback. Require the program to already be installed on the runner. Rejected because a clean runner would then fail every new CLI.

## 2. One instruction, version filled in

- **Decision**: The declared version string replaces every `{version}` token. Catalog files stay `schemas/<tool>/<declared-version>.json`. The resolver in `cli_schema_mcp/src/schema_registry.py` matches those exact stems (`4.22`, `1.31`, `5.2`), so the declared version must not be rewritten to an upstream patch tag.
- **Rationale**: `oc` `latest-4.22`, `kubectl` `stable-1.31.txt`, and the GitHub release lists for kustomize and podman are addressed by the minor already stored in the registration. Renaming schema files to patch versions would break exact minor lookup.
- **Alternatives considered**: Store full patch versions as the schema identity. Rejected because a request for `4.22` looks for a file named `4.22`, not `4.22.17`. One URL copied per version. Rejected by the clarification that one instruction covers every declared version.

## 3. Optional resolved token

- **Decision**: The obtain block may include `version_url` and `version_match`. `{version}` is filled into both first. The check fetches `version_url`, applies `version_match`, and the first capture group replaces `{resolved}` in `artifact_url` and `checksum_url`. When `version_url` is omitted, `{resolved}` equals `{version}`.
- **Rationale**: kubectl’s runnable file is not at a URL that contains only `1.31`; the stable pointer returns `v1.31.x`. Podman and kustomize release tags include a patch. A capture group is data in the registration, not a new Python function per CLI.
- **Alternatives considered**: Hardcode the pointer and GitHub-tag lookups. Rejected as per-CLI code. Require maintainers to paste patch versions into `versions`. Rejected because it changes catalog identity (decision 2).

## 4. Checksum before execution

- **Decision**: `checksum_url` is required. The algorithm is SHA-256. The check accepts a body that is 64 hex digits, or a `sha256sum` listing, using the line whose filename is the artifact URL’s basename. The program is not unpacked or executed unless the digest matches. A missing checksum, a mismatch, or an unreadable body fails that version.
- **Rationale**: The clarification says the same instruction names a checksum and the check runs the program only when it matches. SHA-256 is what the OpenShift, Kubernetes, GitHub release, and podman release assets already publish.
- **Alternatives considered**: Run the download with no proof. Rejected by the clarification. Require a signature chain. Rejected because signing is out of scope for this feature and is not one URL template.

## 5. Generic unpack

- **Decision**: `format` is `raw`, `tar.gz`, or `zip`. `binary` is the installed name for `raw`, or the archive member path otherwise. Unpack at most three layers when a member is itself gzip or a tar, then require that member to be the named binary. The known podman asset is a gzip-compressed tar whose member is the static binary; one `tar.gz` extract plus the member path covers it. No CLI-specific unwrap function.
- **Rationale**: A URL alone is not a runnable program for oc, kustomize, or podman. A shared unpacker with an explicit member path is still one instruction.
- **Alternatives considered**: Shell snippets in the registration. Rejected because the check would execute maintainer shell, which is a larger trust boundary than a checksum-verified archive. Detect format only from the URL suffix. Rejected because a `.tar.gz` URL can still be a tar of another gzip, and an explicit `format` plus a depth cap is testable.

## 6. All-or-nothing publish

- **Decision**: Extract each changed registration into a temporary directory. Copy results into `schemas/` and delete retired version files only after every declared version of every changed registration has succeeded. The job then commits, and only when the actor can push to the head branch. A pull request from a fork never pushes; it prints the catalog paths that differ and exits non-zero. An unchanged catalog does not create an empty commit.
- **Rationale**: FR-008 rejects the whole change when one version fails. Writing schemas as each version finishes would leave a mixed catalog. The current workflow already commits on a same-repo push and fails a pull request whose `schemas/` diff is non-empty; this plan keeps that split and adds the path list the spec requires.
- **Alternatives considered**: Commit after each successful version. Rejected because a later failure would already have published the earlier versions. Always push, including from forks. Rejected because a fork token cannot update the base repository.

## 7. What “changed” means

- **Decision**: A registration is changed when its file is added, modified, or deleted relative to the base revision. Any modification refreshes every version that file declares. Versions present in the base file and absent in the new file are deleted. Deleting the file deletes `schemas/<tool>/`. Files that are not in that set are not read, downloaded, or rewritten.
- **Rationale**: FR-006 and FR-007. Refreshing only the version-list diff would ignore an obtain-URL or adapter edit, which still changes the catalog.
- **Alternatives considered**: Refresh every registration on every run. Rejected because SC-004 requires untouched catalogs to stay identical, and a full refresh of oc is too large for an unrelated edit.

## 8. Time limit

- **Decision**: The job timeout is 90 minutes. That is the planning default for the performance item left open during clarification. One changed registration with several versions fits; a hang fails the job rather than publishing a partial catalog.
- **Rationale**: A single Cobra tree for oc or kubectl is minutes, not seconds. Ninety minutes covers the four current minors of one tool without making “the check finishes” unbounded.
- **Alternatives considered**: No timeout. Rejected because a stuck download would never produce the failure the maintainer is supposed to read. A 20-minute job. Rejected because several oc versions in one registration can exceed it.

## 9. Where the logic lives

- **Decision**: Shared Python in the existing `extractor` package, called by `.github/workflows/extract-schemas.yml`. The workflow does not grow a new `fetch_<tool>` branch. Local validation uses the same entry point as the workflow.
- **Rationale**: Two downloaders would drift. The MCP server must not import `extractor` (constitution II).
- **Alternatives considered**: A longer shell script with generic `curl` only. Rejected because checksum listings, archive members, and the version capture group are easier to test in Python, and the package already owns extraction.
