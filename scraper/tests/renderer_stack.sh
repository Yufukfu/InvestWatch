#!/usr/bin/env bash
# Acceptance check for scraper/compose.renderer.yaml (spec page-rendering, "Run the browser in an isolated container").
# Run from the repository root: scraper/tests/renderer_stack.sh   (needs docker and python3; builds the renderer image)
set -euo pipefail

FILE=scraper/compose.renderer.yaml
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-iw-renderer-check}"
# `config` interpolates the root .env; the renderer needs none of it, so none is passed
compose() { docker compose -f "$FILE" "$@"; }
fail() { echo "FAIL: $*" >&2; exit 1; }
cleanup() { compose down -v --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT

[ -f "$FILE" ] || fail "$FILE does not exist"

echo "== config"
CONFIG="$(compose config --format json)" || fail "compose config is invalid"
printf '%s' "$CONFIG" | python3 -c '
import json, sys
cfg = json.load(sys.stdin)
svc = cfg["services"]["renderer"]
problems = []
if svc.get("ports"): problems.append("publishes a host port")
if svc.get("env_file"): problems.append("uses env_file")
bad = [k for k in svc.get("environment", {}) if k.startswith(("DATABASE", "REDIS", "MINIO", "POSTGRES"))]
if bad: problems.append(f"holds infrastructure variables {bad}")
nets = sorted(svc.get("networks", {}))
if nets != ["egress", "render"]: problems.append("networks are " + str(nets))
if not cfg["networks"]["render"].get("internal"): problems.append("render network is not internal")
if not svc.get("read_only"): problems.append("root filesystem is writable")
if svc.get("cap_drop") != ["ALL"]: problems.append("capabilities are not all dropped")
if "no-new-privileges:true" not in svc.get("security_opt", []): problems.append("no-new-privileges missing")
if not svc.get("shm_size"): problems.append("no shm_size")
limits = svc.get("deploy", {}).get("resources", {}).get("limits", {})
if not limits.get("memory") or not limits.get("cpus"): problems.append("no cpu and memory limits")
if problems:
    print("FAIL: " + "; ".join(problems), file=sys.stderr); sys.exit(1)
print("config ok")
'

echo "== up"
compose up -d --build --wait --wait-timeout 120 renderer
CID="$(compose ps -q renderer)"

echo "== runtime"
[ "$(docker inspect -f '{{.Config.User}}' "$CID")" = "iwr" ] || fail "does not run as the iwr user"
[ -z "$(docker inspect -f '{{json .NetworkSettings.Ports}}' "$CID" | grep -o '"HostPort"' || true)" ] || fail "host port published"
docker inspect -f '{{json .NetworkSettings.Networks}}' "$CID" | python3 -c '
import json, sys
names = sorted(k.rsplit("_", 1)[-1] for k in json.load(sys.stdin))
assert names == ["egress", "render"], names
print("networks", names)
' || fail "container is on the wrong networks"
docker exec "$CID" python -c "import os; print(sorted(k for k in os.environ if k.startswith(('DATABASE','REDIS','MINIO','POSTGRES'))))" | grep -qx "\[\]" || fail "infrastructure variables inside the container"

echo "== health reports the browser version"
VERSION="$(docker exec "$CID" python -c "import json,urllib.request; print(json.load(urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=5))['browser_version'])")"
echo "$VERSION" | grep -Eq '^[0-9]+\.' || fail "health has no browser version: $VERSION"
echo "browser $VERSION"
echo "renderer_stack: ok"
