# Demos: cli-schema-mcp in Practice

Five end-to-end walkthroughs showing how the MCP server prevents CLI command hallucination
in real OpenShift and Kubernetes scenarios. Each demo uses the actual tool responses from
the running server.

---

## Demo 1: CLI not installed → download → validate → execute YAML output

**Scenario**: An agent (or Claude Code) is running in a container or on a fresh machine.
The user asks: *"Get me the YAML config of my myapp deployment in the myproject namespace."*
`oc` is not installed.

**Why it matters without schema grounding**: The agent either fails with an unhelpful error,
or hallucinates a download URL or install command that may not work.

### Step 1 — Detect that the binary is missing

```python
detect_version("oc")
```

```json
{
  "status": "binary_not_found",
  "tool": "oc",
  "message": "'oc' is not installed in this environment.",
  "install_hint": "Download from https://mirror.openshift.com/pub/openshift-v4/clients/ or run: dnf install openshift-clients",
  "suggestion": "Call get_download_info('oc') for version-specific download URLs, or ask the user to install the CLI before retrying."
}
```

### Step 2 — Get the verified download URL

```python
get_download_info("oc", "4.22")
```

```json
{
  "status": "success",
  "tool": "oc",
  "upstream_repo": "https://github.com/openshift/oc",
  "versions": [
    {
      "version": "4.22",
      "artifact_url": "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-4.22/openshift-client-linux.tar.gz",
      "checksum_url": "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-4.22/sha256sum.txt",
      "format": "tar.gz",
      "binary": "oc"
    }
  ],
  "install_notes": "Download the artifact, verify the checksum, and place the binary in your PATH."
}
```

The agent presents this to the user. The user runs:

```bash
# Download and verify
curl -LO https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-4.22/openshift-client-linux.tar.gz
curl -LO https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-4.22/sha256sum.txt
sha256sum --check --ignore-missing sha256sum.txt

# Install
tar xzf openshift-client-linux.tar.gz
sudo mv oc /usr/local/bin/
oc version --client
```

### Step 3 — Validate the command before executing

```python
validate_command("oc", "4.22", "oc get deployment myapp -o yaml -n myproject")
```

```json
{
  "status": "success",
  "tool": "oc",
  "version": "4.22",
  "matched_version": "4.22",
  "command_string": "oc get deployment myapp -o yaml -n myproject",
  "subcommand_context": "'oc get'",
  "valid": true,
  "errors": [],
  "message": "Command is valid"
}
```

### Step 4 — Execute and use the YAML output

The command is validated. The agent executes it and receives YAML:

```bash
oc get deployment myapp -o yaml -n myproject
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: myproject
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    spec:
      containers:
      - name: myapp
        image: registry.example.com/myapp:v2.1.0
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
```

The agent can now parse this YAML to answer questions about the deployment (replica count,
image version, resource requests) without any further schema lookups.

### Agent decision loop

```python
# Pseudocode for the agent
result = detect_version("oc")
if result["status"] == "binary_not_found":
    info = get_download_info("oc", target_version)
    tell_user(info["versions"][0]["artifact_url"], info["install_notes"])
    wait_for_user_confirmation()

# User has installed oc
cmd = f"oc get deployment {deployment_name} -o yaml -n {namespace}"
validation = validate_command("oc", target_version, cmd)
if validation["valid"]:
    yaml_output = run_in_shell(cmd)
    parse_and_answer(yaml_output)
else:
    report_errors(validation["errors"])
```

---

## Demo 2: Flag hallucination caught before execution

**Scenario**: An autonomous pipeline (Event-Driven Ansible, OpenShift Lightspeed) generates
an `oc` command to restart a deployment. No human reviews it before execution.

**Why it matters**: `--force` sounds plausible on `oc rollout restart` — it exists on many
other commands. Without schema grounding, the command runs and may fail silently or throw a
confusing error at 2 a.m. during an incident.

### Step 1 — Agent proposes a command

The LLM generates:
```
oc rollout restart deployment/myapp --force
```

### Step 2 — Validate before execution

```python
validate_command("oc", "4.22", "oc rollout restart deployment/myapp --force")
```

```json
{
  "status": "success",
  "tool": "oc",
  "version": "4.22",
  "valid": false,
  "errors": [
    "--force is not a valid flag for 'oc rollout restart' in version 4.22"
  ],
  "message": "1 invalid flag(s) found"
}
```

**The command is stopped before it runs.**

### Step 3 — Look up the real flags and re-plan

```python
get_flags("oc", "4.22", "rollout restart")
```

Returns the actual available flags: `--dry-run`, `--filename/-f`, `--selector/-l`,
`--timeout`, and others. `--force` is absent — it does not exist for this subcommand.

The agent rebuilds the command using only verified flags:

```python
validate_command("oc", "4.22", "oc rollout restart deployment/myapp -n prod")
```

```json
{
  "valid": true,
  "errors": [],
  "message": "Command is valid"
}
```

### Step 4 — Execute with confidence

```bash
oc rollout restart deployment/myapp -n prod
```

**Result**: The autonomous pipeline executes the correct command. The hallucinated `--force`
never reaches the cluster.

---

## Demo 3: Real-world OpenShift Logging commands with hyphenated names

**Scenario**: An agent is helping debug a Vector log collector in the `openshift-logging`
namespace. The namespace name, pod name, and config filename all contain hyphens.

**Why it matters**: Before v0.1.3, `validate_command` would reject these 100% valid commands
because the regex flag parser matched hyphens inside token values as flag prefixes. This was
the original bug that surfaced while wiring cli-schema-mcp into
[tosins-rhel-assistant](https://github.com/tosin2013/tosins-rhel-assistant).

### Commands that now validate correctly

```python
validate_command("oc", "4.22", "oc logs -n openshift-logging -l component=vector -c vector")
```
```json
{ "valid": true, "errors": [] }
```

The namespace value `openshift-logging` is a positional argument to `-n`, not a flag.

```python
validate_command("oc", "4.22", "oc apply -f vector-tuning.yaml")
```
```json
{ "valid": true, "errors": [] }
```

The filename `vector-tuning.yaml` is a positional argument to `-f`, not a flag.

```python
validate_command("oc", "4.22", "oc exec vector-abc123 -- cat /var/lib/vector/checkpoints.json")
```
```json
{ "valid": true, "errors": [] }
```

`vector-abc123` is the pod name (positional arg). `--` is the POSIX end-of-flags separator —
everything after it is a literal command, not a flag.

### Suggested follow-up workflow

Once validation passes, the agent can chain these commands to diagnose the log collector:

```bash
# Check collector logs
oc logs -n openshift-logging -l component=vector -c vector --tail=50

# Apply a tuning config
oc apply -f vector-tuning.yaml

# Inspect a checkpoint file inside the running pod
oc exec vector-abc123 -- cat /var/lib/vector/checkpoints.json
```

---

## Demo 4: Version detection → version-appropriate flag lookup

**Scenario**: A developer asks Claude Code: *"How do I pause and resume a rollout in oc?"*
They haven't specified which version they're running.

**Why it matters**: Flag names and availability differ between oc 4.18 and 4.22. Without
version detection, the agent might give flags valid in one version but not another.

### Step 1 — Detect the installed version

```python
detect_version("oc")
```

```json
{
  "status": "success",
  "tool": "oc",
  "version": "4.22.1",
  "matched_schema": "4.22",
  "message": "Detected oc 4.22.1, using schema 4.22"
}
```

The agent now knows to use schema version `4.22` for all subsequent calls — no version
guessing required.

### Step 2 — Browse the rollout subcommands

```python
list_subcommands("oc", "4.22", "rollout")
```

```json
{
  "status": "success",
  "tool": "oc",
  "version": "4.22",
  "parent": "rollout",
  "subcommands": ["cancel", "history", "latest", "pause", "restart", "resume", "retry", "status", "undo"],
  "message": "Found 9 subcommands under 'rollout'"
}
```

`pause` and `resume` are both present. The agent can now answer the user's question with
certainty and offer to run the commands.

### Step 3 — Validate before executing

```python
validate_command("oc", "4.22", "oc rollout pause deployment/myapp -n prod")
```
```json
{ "valid": true, "errors": [] }
```

```python
validate_command("oc", "4.22", "oc rollout resume deployment/myapp -n prod")
```
```json
{ "valid": true, "errors": [] }
```

**Result**: The agent confidently presents the correct, version-verified commands and
optionally executes them.

---

## Demo 5: Air-gapped OCP cluster — full offline workflow

**Scenario**: A regulated enterprise runs OpenShift in a cluster with no internet access at
runtime. The team deploys cli-schema-mcp as a grounding backend for their AI tooling. CLIs
needed for operations must also be sourced without internet access.

**Why it matters**: Without an offline schema source, AI tooling either can't validate CLI
commands or must reach back to GitHub — both unacceptable in air-gapped environments.

### Step 1 — Pull the OCI schema artifact (internet-connected machine)

```bash
# On a machine that can reach quay.io:
oras pull quay.io/takinosh/cli-schema-mcp:v0.1.4 --output /tmp/schemas-pull
tar -xzf /tmp/schemas-pull/schemas.tar.gz -C /opt/cli-schemas

# Transfer to internal registry or air-gapped machine
scp -r /opt/cli-schemas airgapped-host:/opt/cli-schemas
```

### Step 2 — Start the MCP server against the pulled registry

```bash
# On the air-gapped machine (no internet needed):
SCHEMA_REGISTRY_PATH=/opt/cli-schemas cli-schema-mcp
```

### Step 3 — Verify all CLIs are available

```python
list_supported()
```

```json
{
  "status": "success",
  "total_tools": 7,
  "total_schemas": 21,
  "tools": {
    "kubectl":   ["1.31", "1.32", "1.33", "1.34", "1.35"],
    "kustomize": ["5.3", "5.4", "5.5"],
    "nmstatectl": ["2.2"],
    "oc":        ["4.18", "4.19", "4.20", "4.21", "4.22"],
    "podman":    ["5.2", "5.3", "5.4"],
    "tkn":       ["0.45", "0.46"],
    "virtctl":   ["1.8", "1.9"]
  }
}
```

All 7 CLIs and 21 schema versions are available — fully offline.

### Step 4 — Agent guides CLI installation without internet

When an operator needs `oc` and it isn't installed on a node:

```python
get_download_info("oc", "4.22")
```

```json
{
  "artifact_url": "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-4.22/openshift-client-linux.tar.gz",
  "checksum_url": "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-4.22/sha256sum.txt",
  "format": "tar.gz",
  "binary": "oc"
}
```

The operator downloads the binary on an internet-connected machine, verifies the SHA-256
checksum, and transfers it to the air-gapped node. The MCP server provides the exact URL —
no guessing.

### Step 5 — Validate and execute normally

With `oc` installed on the node, all six MCP tools work identically to the internet-connected
case. The server never downloads anything at runtime.

**Result**: Full CLI flag grounding in a completely disconnected environment.

---

## Quick reference: which tool for which situation

| Situation | Tool to call |
|-----------|-------------|
| "What CLIs do you support?" | `list_supported()` |
| "What version of oc am I running?" | `detect_version("oc")` |
| "oc isn't installed — where do I get it?" | `detect_version` → `get_download_info` |
| "What subcommands does `oc rollout` have?" | `list_subcommands("oc", "4.22", "rollout")` |
| "What flags can I use with `oc rollout restart`?" | `get_flags("oc", "4.22", "rollout restart")` |
| "Is this command correct?" | `validate_command("oc", "4.22", "oc rollout restart ...")` |

---

## What's next

| Topic | Link |
|-------|-------|
| Tool reference with real outputs | [Tutorial](tutorial.md) |
| Architecture and tool layer | [Architecture](architecture.md) |
| Deploying in a container / OCP | [Deployment](deployment.md) |
| Adding a new CLI to the registry | [Tutorial — Adding your first CLI](tutorial.md#adding-your-first-cli) |
| Contributing guide | [CONTRIBUTING.md](../CONTRIBUTING.md) |
