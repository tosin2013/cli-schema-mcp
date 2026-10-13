#!/usr/bin/env bash
# Download each declared CLI version and run `python -m extractor`.
# Used locally and by .github/workflows/extract-schemas.yml.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BIN_ROOT="${BIN_ROOT:-/tmp/cli-schema-bins}"
PYTHON="${PYTHON:-python3}"
mkdir -p "$BIN_ROOT"

log() { printf '%s\n' "$*"; }

download() {
  local url="$1" dest="$2"
  curl -fsSL --retry 3 --retry-delay 2 --max-time 180 -o "$dest" "$url"
}

fetch_oc() {
  local minor="$1"
  local dest="${BIN_ROOT}/oc-${minor}"
  mkdir -p "$dest"
  if [[ -x "${dest}/oc" ]]; then
    return
  fi
  local tmp
  tmp="$(mktemp -d)"
  local url_linux="https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-${minor}/openshift-client-linux.tar.gz"
  local url_amd64="https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest-${minor}/openshift-client-linux-amd64.tar.gz"
  if ! download "$url_linux" "${tmp}/oc.tgz"; then
    download "$url_amd64" "${tmp}/oc.tgz"
  fi
  tar -xzf "${tmp}/oc.tgz" -C "$dest" oc
  chmod +x "${dest}/oc"
  rm -rf "$tmp"
}

fetch_kubectl() {
  local minor="$1"
  local dest="${BIN_ROOT}/kubectl-${minor}"
  mkdir -p "$dest"
  if [[ -x "${dest}/kubectl" ]]; then
    return
  fi
  local ver
  ver="$(curl -fsSL --retry 3 --max-time 60 "https://dl.k8s.io/release/stable-${minor}.txt")"
  ver="${ver//$'\r'/}"
  download "https://dl.k8s.io/release/${ver}/bin/linux/amd64/kubectl" "${dest}/kubectl"
  chmod +x "${dest}/kubectl"
}

latest_github_tag() {
  local repo="$1" pattern="$2"
  curl -fsSL --retry 3 --max-time 60 \
    "https://api.github.com/repos/${repo}/releases?per_page=100" \
    | "$PYTHON" -c '
import json, re, sys
pattern = re.compile(sys.argv[1])
releases = json.load(sys.stdin)
found = []
for release in releases:
    tag = release.get("tag_name") or ""
    match = pattern.fullmatch(tag)
    if match:
        found.append(match.group(1))
if not found:
    sys.exit("no release matched")
def key(value):
    return [int(part) for part in value.split(".")]
print(sorted(found, key=key)[-1])
' "$pattern"
}

fetch_kustomize() {
  local minor="$1"
  local dest="${BIN_ROOT}/kustomize-${minor}"
  mkdir -p "$dest"
  if [[ -x "${dest}/kustomize" ]]; then
    return
  fi
  local ver
  ver="$(latest_github_tag "kubernetes-sigs/kustomize" "kustomize/v(${minor//./\\.}\\.[0-9]+)")"
  local tmp
  tmp="$(mktemp -d)"
  download \
    "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${ver}/kustomize_v${ver}_linux_amd64.tar.gz" \
    "${tmp}/kustomize.tgz"
  tar -xzf "${tmp}/kustomize.tgz" -C "$dest" kustomize
  chmod +x "${dest}/kustomize"
  rm -rf "$tmp"
}

fetch_podman() {
  local minor="$1"
  local dest="${BIN_ROOT}/podman-${minor}"
  mkdir -p "$dest"
  if [[ -x "${dest}/podman" ]] && file -b "${dest}/podman" | grep -q 'ELF'; then
    return
  fi
  local ver
  ver="$(latest_github_tag "containers/podman" "v(${minor//./\\.}\\.[0-9]+)")"
  local tmp
  tmp="$(mktemp -d)"
  download \
    "https://github.com/containers/podman/releases/download/v${ver}/podman-remote-static-linux_amd64.tar.gz" \
    "${tmp}/podman.tgz"
  tar -xzf "${tmp}/podman.tgz" -C "$tmp"
  local bin
  bin="$(find "$tmp" -type f ! -name 'podman.tgz' | head -n 1)"
  if [[ -z "$bin" ]]; then
    echo "podman archive for ${ver} was empty" >&2
    exit 1
  fi
  # Release tarballs nest a gzip, then a tar, then the static ELF.
  local current="$bin"
  local round
  for round in 1 2 3 4; do
    local kind
    kind="$(file -b "$current")"
    if [[ "$kind" == *gzip* ]]; then
      local unzipped="${tmp}/unzipped-${round}"
      gzip -dc "$current" > "$unzipped"
      current="$unzipped"
      continue
    fi
    if [[ "$kind" == *tar* ]]; then
      local unpacked="${tmp}/unpacked-${round}"
      mkdir -p "$unpacked"
      tar -xf "$current" -C "$unpacked"
      current="$(find "$unpacked" -type f | head -n 1)"
      continue
    fi
    break
  done
  if ! file -b "$current" | grep -q 'ELF'; then
    echo "podman ${ver} did not unpack to an ELF binary: $(file -b "$current")" >&2
    exit 1
  fi
  install -m 0755 "$current" "${dest}/podman"
  rm -rf "$tmp"
}

extract_one() {
  local name="$1" version="$2" bindir="$3"
  log "Extracting ${name} ${version} using ${bindir}"
  PATH="${bindir}:${PATH}" "$PYTHON" -u -m extractor "$name" "$version"
}

# Prefer a matching binary already on PATH so local installs are reused.
use_local_if_match() {
  local binary="$1" minor="$2" dest="$3"
  if ! command -v "$binary" >/dev/null 2>&1; then
    return 1
  fi
  local detected
  detected="$("$binary" version --client 2>/dev/null || "$binary" version 2>/dev/null || true)"
  if [[ "$detected" == *"${minor}"* ]]; then
    mkdir -p "$dest"
    ln -sfn "$(command -v "$binary")" "${dest}/${binary}"
    return 0
  fi
  return 1
}

log "Preparing oc clients"
for minor in 4.18 4.19 4.20 4.21 4.22; do
  if ! use_local_if_match oc "$minor" "${BIN_ROOT}/oc-${minor}"; then
    fetch_oc "$minor"
  fi
done

log "Preparing kubectl clients"
for minor in 1.31 1.32 1.33 1.34 1.35; do
  if ! use_local_if_match kubectl "$minor" "${BIN_ROOT}/kubectl-${minor}"; then
    fetch_kubectl "$minor"
  fi
done

log "Preparing kustomize clients"
for minor in 5.3 5.4 5.5; do
  if ! use_local_if_match kustomize "$minor" "${BIN_ROOT}/kustomize-${minor}"; then
    fetch_kustomize "$minor"
  fi
done

log "Preparing podman clients"
for minor in 5.2 5.3 5.4; do
  if ! use_local_if_match podman "$minor" "${BIN_ROOT}/podman-${minor}"; then
    fetch_podman "$minor"
  fi
done

log "Extracting schemas"
for minor in 4.18 4.19 4.20 4.21 4.22; do
  extract_one oc "$minor" "${BIN_ROOT}/oc-${minor}"
done
for minor in 1.31 1.32 1.33 1.34 1.35; do
  extract_one kubectl "$minor" "${BIN_ROOT}/kubectl-${minor}"
done
for minor in 5.3 5.4 5.5; do
  extract_one kustomize "$minor" "${BIN_ROOT}/kustomize-${minor}"
done
for minor in 5.2 5.3 5.4; do
  extract_one podman "$minor" "${BIN_ROOT}/podman-${minor}"
done

"$PYTHON" - << 'PY'
import json
from pathlib import Path

def flags(node, path):
    if path == []:
        return {f["name"] for f in node.get("flags", [])}
    for child in node.get("subcommands", []):
        if child.get("name") == path[0]:
            return flags(child, path[1:])
    raise SystemExit(f"missing path {path} in schema")

oc = json.loads(Path("schemas/oc/4.22.json").read_text())
names = flags(oc, ["rollout", "restart"])
missing = {"--selector", "--filename", "--namespace"} - names
if missing or "--force" in names:
    raise SystemExit(f"oc 4.22 rollout restart flags unexpected: missing={missing} force={'--force' in names}")
required = [
    "schemas/oc/4.18.json", "schemas/oc/4.19.json", "schemas/oc/4.20.json",
    "schemas/oc/4.21.json", "schemas/oc/4.22.json",
    "schemas/kubectl/1.31.json", "schemas/kubectl/1.32.json", "schemas/kubectl/1.33.json",
    "schemas/kubectl/1.34.json", "schemas/kubectl/1.35.json",
    "schemas/kustomize/5.3.json", "schemas/kustomize/5.4.json", "schemas/kustomize/5.5.json",
    "schemas/podman/5.2.json", "schemas/podman/5.3.json", "schemas/podman/5.4.json",
]
absent = [path for path in required if not Path(path).is_file()]
if absent:
    raise SystemExit("missing schemas: " + ", ".join(absent))
print("schema smoke check passed")
PY

log "All schemas extracted"
