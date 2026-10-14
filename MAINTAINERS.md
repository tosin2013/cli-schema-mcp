# Maintainers

## Project Maintainers

| GitHub | Role |
|---|---|
| @tosin2013 | Project Lead |

## CLI Schema Maintainers

Each CLI in the registry has designated maintainers who review schema PRs for that tool.
Community contributors are encouraged to maintain the CLIs they add.

| CLI | Versions | Maintainer(s) |
|---|---|---|
| `oc` | 4.18–4.22 | @tosin2013 |
| `kubectl` | 1.31–1.35 | community |
| `kustomize` | 5.3–5.5 | community |
| `podman` | 5.2–5.4 | community |
| `tkn` | 0.45–0.46 | community |
| `virtctl` | 1.8–1.9 | community |

## Becoming a CLI Maintainer

After you add a CLI via PR, you are automatically listed as its maintainer in `clis/<name>.yaml`.
CLI maintainers are expected to:

- Open a PR when a new minor version of the CLI is released
- Verify flag accuracy when schema diffs are flagged in PR review
- Respond to issues tagged with your CLI's name within 30 days

To add yourself as a maintainer for a CLI, add your GitHub username to the `maintainers` field in
`clis/<name>.yaml` and open a PR.
