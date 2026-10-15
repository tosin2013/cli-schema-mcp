# Declarative Network Management with nmstate — Guided by cli-schema-mcp

**Date**: 2026-10-15  
**Tags**: nmstate, networking, MCP, OpenShift, RHEL, declarative

---

Network configuration has historically meant running a sequence of imperative commands
(`ip link`, `nmcli con add`, `ifconfig`) and hoping you remembered every flag correctly.
`nmstate` flips that model: you describe the network state you *want* in a YAML file, and
`nmstatectl apply` makes it so — atomically, with automatic rollback if verification fails.

This post walks through real `nmstate` workflows, using `cli-schema-mcp` as the grounding
layer to discover subcommands, look up flags, and validate every command before it touches
the network.

---

## Setting up

### Install nmstate

nmstate is a system package — install it with your package manager:

```bash
# RHEL / Fedora / CentOS Stream
sudo dnf install nmstate

# Verify
nmstatectl version
```

If you're using an AI agent that calls `get_download_info`, it will tell you exactly this:

```python
get_download_info("nmstate")
```

```json
{
  "status": "success",
  "tool": "nmstate",
  "install_method": "system_package",
  "install_notes": "'nmstate' is a system package with no automated download URL. Install via your package manager (e.g. dnf install nmstate) or see https://github.com/nmstate/nmstate for instructions.",
  "upstream_repo": "https://github.com/nmstate/nmstate"
}
```

### Discover what nmstatectl can do

```python
list_subcommands("nmstate", "2.2")
```

```json
{
  "status": "success",
  "tool": "nmstate",
  "version": "2.2",
  "subcommands": [
    "apply",    "autoconf", "commit",   "edit",
    "format",   "gc",       "gr",       "policy",
    "rollback", "service",  "show",     "statistic",
    "validate", "version"
  ],
  "message": "Found 14 subcommands under 'nmstate'"
}
```

The key workflow subcommands are **show**, **apply**, **validate**, **commit**, and **rollback**.

---

## Viewing current network state

Before changing anything, see what nmstate already knows:

```bash
# Show full current state (YAML)
nmstatectl show

# Show state for one interface
nmstatectl show eth0

# Show in JSON format
nmstatectl show --json
```

The flags available for `show`:

```python
get_flags("nmstate", "2.2", "show")
```

| Flag | Description |
|------|-------------|
| `--json` | Show state in JSON format (default is YAML) |
| `--kernel` | Show kernel network state only |
| `--running-config` | Show running configuration only |
| `--show-secrets` | Show secrets (hidden by default) |

Validate before running:

```python
validate_command("nmstate", "2.2", "nmstatectl show eth0")
```
```json
{ "valid": true, "errors": [] }
```

### Sample output

```yaml
---
dns-resolver:
  config: {}
  running:
    search: []
    server:
    - 192.168.1.1
interfaces:
- name: eth0
  type: ethernet
  state: up
  ipv4:
    enabled: true
    address:
    - ip: 192.168.1.100
      prefix-length: 24
    dhcp: false
  ipv6:
    enabled: false
routes:
  config:
  - destination: 0.0.0.0/0
    next-hop-address: 192.168.1.1
    next-hop-interface: eth0
```

This YAML is the *desired state* format. You can capture it, edit it, and apply it back.

---

## Applying network state: YAML examples

The `apply` subcommand is the heart of nmstate. Available flags:

```python
get_flags("nmstate", "2.2", "apply")
```

| Flag | Description |
|------|-------------|
| `--no-commit` | Apply the state but don't commit — leaves a checkpoint for manual rollback |
| `--no-verify` | Skip post-apply verification and disable automatic rollback |
| `--memory-only` | Apply to kernel only, do not persist across reboots |
| `--kernel` | Apply to kernel network stack only |
| `--override-iface` | Override interface settings without merging current state |

### Example 1: Configure a static IP address

```yaml
# eth0-static.yaml
---
interfaces:
- name: eth0
  type: ethernet
  state: up
  ipv4:
    enabled: true
    dhcp: false
    address:
    - ip: 10.0.1.50
      prefix-length: 24
  ipv6:
    enabled: false
routes:
  config:
  - destination: 0.0.0.0/0
    next-hop-address: 10.0.1.1
    next-hop-interface: eth0
dns-resolver:
  config:
    server:
    - 8.8.8.8
    - 8.8.4.4
```

Before applying, validate the command:

```python
validate_command("nmstate", "2.2", "nmstatectl apply /tmp/eth0-static.yaml")
```
```json
{ "valid": true, "errors": [] }
```

Apply it:

```bash
nmstatectl apply /tmp/eth0-static.yaml
```

nmstate applies the state, verifies it converged, and commits automatically. If verification
fails, it rolls back to the previous state.

---

### Example 2: Create a bond for high availability

```yaml
# bond0-active-backup.yaml
---
interfaces:
- name: bond0
  type: bond
  state: up
  ipv4:
    enabled: true
    dhcp: true
  link-aggregation:
    mode: active-backup
    port:
    - eth0
    - eth1
    options:
      miimon: "140"
- name: eth0
  type: ethernet
  state: up
- name: eth1
  type: ethernet
  state: up
```

Use `--no-commit` to test before finalising:

```python
validate_command("nmstate", "2.2", "nmstatectl apply /tmp/bond0-active-backup.yaml --no-commit")
```
```json
{ "valid": true, "errors": [] }
```

```bash
# Apply without committing — leaves a rollback checkpoint
nmstatectl apply /tmp/bond0-active-backup.yaml --no-commit

# Inspect the result
nmstatectl show bond0

# If satisfied:
nmstatectl commit

# If not satisfied:
nmstatectl rollback
```

Both `commit` and `rollback` validate correctly:

```python
validate_command("nmstate", "2.2", "nmstatectl commit")   # valid: true
validate_command("nmstate", "2.2", "nmstatectl rollback") # valid: true
```

---

### Example 3: Add a VLAN interface

```yaml
# vlan100.yaml
---
interfaces:
- name: eth0.100
  type: vlan
  state: up
  vlan:
    base-iface: eth0
    id: 100
  ipv4:
    enabled: true
    dhcp: false
    address:
    - ip: 172.16.100.10
      prefix-length: 24
```

Test without rebooting to verify persistence:

```python
validate_command("nmstate", "2.2", "nmstatectl apply /tmp/vlan100.yaml --memory-only")
```
```json
{ "valid": true, "errors": [] }
```

```bash
# Test in memory only (lost on reboot)
nmstatectl apply /tmp/vlan100.yaml --memory-only

# If good, apply persistently
nmstatectl apply /tmp/vlan100.yaml
```

---

### Example 4: Configure OVS bridge (OpenShift)

For OpenShift nodes using OVS:

```yaml
# ovs-br0.yaml
---
interfaces:
- name: ovs-br0
  type: ovs-bridge
  state: up
  bridge:
    options:
      stp: false
    port:
    - name: eth0
- name: eth0
  type: ethernet
  state: up
  ipv4:
    enabled: false
```

```bash
nmstatectl apply /tmp/ovs-br0.yaml
```

---

### Example 5: Remove an interface

To cleanly remove a VLAN or virtual interface:

```yaml
# remove-vlan100.yaml
---
interfaces:
- name: eth0.100
  type: vlan
  state: absent
```

```python
validate_command("nmstate", "2.2", "nmstatectl apply /tmp/remove-vlan100.yaml")
```
```json
{ "valid": true, "errors": [] }
```

```bash
nmstatectl apply /tmp/remove-vlan100.yaml
```

---

## Validate YAML before applying

Use `nmstatectl validate` to check a YAML file without touching the network — useful in CI
pipelines before pushing network configs to nodes.

```python
validate_command("nmstate", "2.2", "nmstatectl validate /tmp/eth0-static.yaml")
```
```json
{ "valid": true, "errors": [] }
```

```bash
nmstatectl validate /tmp/eth0-static.yaml
# No output = valid
# Non-zero exit code = invalid YAML or unsupported fields
```

Combine this in a CI script:

```bash
for f in network-configs/*.yaml; do
  echo -n "Validating $f ... "
  nmstatectl validate "$f" && echo "OK" || echo "FAILED"
done
```

---

## The MCP-guided agent workflow

When an AI agent is helping configure network state, the MCP server provides the guardrails:

```
User: "Set a static IP of 10.0.1.50/24 on eth0 with gateway 10.0.1.1"

Agent → list_subcommands("nmstate", "2.2")
     ← subcommands: [apply, show, validate, commit, rollback, ...]

Agent → get_flags("nmstate", "2.2", "apply")
     ← --no-commit (apply without committing), --memory-only, --no-verify

Agent generates eth0-static.yaml (YAML above)

Agent → validate_command("nmstate", "2.2", "nmstatectl apply /tmp/eth0-static.yaml --no-commit")
     ← valid: true, errors: []

Agent → executes: nmstatectl apply /tmp/eth0-static.yaml --no-commit
Agent → executes: nmstatectl show eth0  (verify it looks right)
Agent → asks user: "Configuration looks correct. Commit permanently? (y/n)"
User → y
Agent → executes: nmstatectl commit
```

At no point does the agent invent a flag or subcommand that doesn't exist.

---

## Key nmstate YAML schema reference

| Field | Values | Description |
|-------|--------|-------------|
| `interfaces[].state` | `up`, `down`, `absent` | Desired interface state |
| `interfaces[].type` | `ethernet`, `bond`, `vlan`, `ovs-bridge`, `bridge` | Interface type |
| `interfaces[].ipv4.dhcp` | `true`, `false` | Enable DHCP for IPv4 |
| `interfaces[].ipv4.address[].ip` | `x.x.x.x` | Static IPv4 address |
| `interfaces[].ipv4.address[].prefix-length` | `0-32` | Subnet prefix |
| `link-aggregation.mode` | `active-backup`, `balance-rr`, `802.3ad`, `balance-tlb` | Bond mode |
| `routes.config[].destination` | CIDR | Route destination |
| `routes.config[].next-hop-address` | IP | Gateway address |
| `dns-resolver.config.server` | list of IPs | DNS servers |

---

## Further reading

- [nmstate documentation](https://nmstate.io/user/index.html)
- [nmstate GitHub](https://github.com/nmstate/nmstate)
- [cli-schema-mcp demos](../demos.md) — more MCP-guided CLI workflows
- [cli-schema-mcp tutorial](../tutorial.md) — all six MCP tools explained
