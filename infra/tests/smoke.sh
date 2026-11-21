#!/usr/bin/env bash
# Smoke test for the shared infrastructure (openspec/changes/infra-compose, spec shared-infrastructure).
# Runs against throwaway compose projects with their own env file and ports, and removes them
# (containers, networks, volumes) on exit. Needs only bash and Docker.
#
#   infra/tests/smoke.sh                 all groups except the LLM download
#   infra/tests/smoke.sh parallel redis  selected groups
#   SMOKE_LLM=1 infra/tests/smoke.sh llm also pulls gemma3:4b (several GB)
set -euo pipefail
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
INFRA="$ROOT/infra/compose.yaml"
PROBE_IMAGE=public.ecr.aws/docker/library/alpine:3.22
TMP=$(mktemp -d)
# Git Bash: hand Docker a Windows path (C:/...), since path conversion is off above.
if command -v cygpath >/dev/null 2>&1; then TMP=$(cygpath -m "$TMP"); ROOT=$(cygpath -m "$ROOT"); INFRA="$ROOT/infra/compose.yaml"; fi
RUN_ID="s$$"
PROJECTS=()
FAILS=0
PASSES=0

log() { printf '%s\n' "$*" >&2; }
pass() { PASSES=$((PASSES + 1)); log "PASS  $*"; }
fail() { FAILS=$((FAILS + 1)); log "FAIL  $*"; }
check() { # check "<name>" cmd...  (passes when cmd exits 0)
  local name=$1; shift
  if "$@" >"$TMP/last.out" 2>&1; then pass "$name"; else fail "$name"; sed 's/^/      /' "$TMP/last.out" | tail -n 15 >&2; fi
}

cleanup() {
  local p
  for p in "${PROJECTS[@]:-}"; do
    [ -n "$p" ] || continue
    docker compose -p "$p" --env-file "$TMP/$p.env" -f "$INFRA" --profile llm down -v --remove-orphans >/dev/null 2>&1 || true
  done
  rm -rf "$TMP"
}
trap cleanup EXIT

# new_env <project> <https-port> <http-port>: env file from .env.example, every empty secret filled with random hex.
new_env() {
  local p=$1 f="$TMP/$1.env"
  "$ROOT/scripts/init-env.sh" "$f" >/dev/null
  sed -i -e "s|^COMPOSE_PROJECT_NAME=.*|COMPOSE_PROJECT_NAME=$p|" -e "s|^IW_HTTPS_PORT=.*|IW_HTTPS_PORT=$2|" \
    -e "s|^IW_HTTP_PORT=.*|IW_HTTP_PORT=$3|" "$f"
  echo "$f"
}

# dc <project> [compose args...]: docker compose for that project, infra file only.
dc() { local p=$1; shift; docker compose -p "$p" --env-file "$TMP/$p.env" -f "$INFRA" "$@"; }

# up <project> <https> <http> [extra compose -f files...] -- [services...]
up() {
  local p=$1 hs=$2 hp=$3; shift 3
  PROJECTS+=("$p")
  new_env "$p" "$hs" "$hp" >/dev/null
  dc "$p" up -d --wait --wait-timeout 180 "$@"
}

# probe <network> <cmd...>: run a throwaway alpine container on a network.
probe() { local net=$1; shift; docker run --rm --network "$net" "$PROBE_IMAGE" "$@"; }

container_ip() { # container_ip <project> <service> <network>
  docker inspect -f "{{(index .NetworkSettings.Networks \"$3\").IPAddress}}" "$(dc "$1" ps -q "$2")"
}

# ---------------------------------------------------------------- groups

two_stacks_up() {
  up "$1" 18443 18080 postgres gateway && up "$2" 18444 18081 postgres gateway
}
own_networks() {
  local nets n; nets=$(docker network ls --format '{{.Name}}')
  for n in "$1_data" "$1_edge" "$2_data" "$2_edge"; do
    echo "$nets" | grep -qx "$n" || { echo "missing network $n"; echo "$nets"; return 1; }
  done
}
resolves_to_own() { # resolves_to_own <project> <service> <network-suffix>
  local want got
  want=$(container_ip "$1" "$2" "$1_$3")
  got=$(probe "$1_$3" getent ahostsv4 "$2" | awk '{print $1}' | sort -u | tr '\n' ' ')
  echo "want=$want got=$got"; [ -n "$want" ] && [ "$got" = "$want " ]
}

group_parallel() {
  local a="iw-smoke-a-$RUN_ID" b="iw-smoke-b-$RUN_ID"
  check "two stacks start at once on different gateway ports" two_stacks_up "$a" "$b"
  check "each stack has its own data and edge networks" own_networks "$a" "$b"
  check "postgres resolves only to its own stack" resolves_to_own "$a" postgres data
}

SECRETS=(POSTGRES_ADMIN_PASSWORD POSTGRES_APP_PASSWORD REDIS_PASSWORD MINIO_ROOT_PASSWORD MINIO_SECRET_KEY)

example_lists_secrets() {
  local v; for v in "${SECRETS[@]}"; do
    grep -qx "$v=" "$ROOT/.env.example" || { echo "$v missing or not empty in .env.example"; return 1; }
  done
}
generated_env_complete() {
  local f="$TMP/gen.env" v val
  "$ROOT/scripts/init-env.sh" "$f" || return 1
  for v in $(grep -E '^[A-Z0-9_]+(_PASSWORD|_SECRET_KEY)=' "$ROOT/.env.example" | cut -d= -f1); do
    val=$(grep -E "^$v=" "$f" | cut -d= -f2-)
    [ ${#val} -ge 32 ] || { echo "$v has ${#val} chars"; return 1; }
  done
  docker compose --env-file "$f" -f "$ROOT/compose.yaml" config -q
}
init_env_no_overwrite() {
  local f="$TMP/keep.env"; echo KEEP=1 >"$f"
  ! "$ROOT/scripts/init-env.sh" "$f" && grep -qx KEEP=1 "$f"
}
init_env_relative_to_caller() {
  local d="$TMP/rel" name="smoke-rel-$RUN_ID.env"; mkdir -p "$d"
  (cd "$d" && "$ROOT/scripts/init-env.sh" "$name") || return 1
  [ -f "$d/$name" ] && [ ! -e "$ROOT/$name" ] || { rm -f "$ROOT/$name"; echo "written to the repo root"; return 1; }
}
init_env_crlf() { # a CRLF .env.example (Windows autocrlf) still gets every secret filled
  local r="$TMP/crlf" v val; mkdir -p "$r/scripts"
  cp "$ROOT/scripts/init-env.sh" "$r/scripts/"; sed 's/$/\r/' "$ROOT/.env.example" >"$r/.env.example"
  "$r/scripts/init-env.sh" "$r/out.env" >/dev/null || return 1
  for v in "${SECRETS[@]}"; do
    val=$(grep -E "^$v=" "$r/out.env" | cut -d= -f2- | tr -d '\r')
    [ ${#val} -ge 32 ] || { echo "$v has ${#val} chars"; return 1; }
  done
}
# requires_secret <VAR> [compose file]: compose config fails, naming VAR, when VAR is empty.
requires_secret() {
  local v=$1 file=${2:-$ROOT/compose.yaml} f="$TMP/req-$1.env"
  "$ROOT/scripts/init-env.sh" "$f" >/dev/null
  sed -i "s|^$v=.*|$v=|" "$f"
  if docker compose --env-file "$f" -f "$file" config -q 2>"$f.err"; then echo "config succeeded without $v"; return 1; fi
  grep -q "$v" "$f.err" || { cat "$f.err"; return 1; }
}

group_env() {
  check ".env.example lists every infrastructure secret, empty" example_lists_secrets
  check "init-env fills every secret with 32+ chars and compose config accepts it" generated_env_complete
  check "init-env never overwrites an existing file" init_env_no_overwrite
  check "init-env resolves a relative path from the caller's directory" init_env_relative_to_caller
  check "init-env fills secrets from a CRLF .env.example" init_env_crlf
  check "missing POSTGRES_APP_PASSWORD is named" requires_secret POSTGRES_APP_PASSWORD
}

# rcli <project> [args...]: redis-cli inside the redis container, authenticated from its own env.
rcli() { local p=$1; shift; dc "$p" exec -T redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli "$@"' rcli "$@"; }
redis_auth() {
  local got; got=$(rcli "$1" ping); echo "auth ping: $got"; [ "$got" = PONG ] || return 1
  got=$(dc "$1" exec -T redis redis-cli ping 2>&1 || true); echo "no-auth ping: $got"
  echo "$got" | grep -q NOAUTH
}
redis_config() {
  local aof pol
  aof=$(rcli "$1" config get appendonly | tail -n 1); pol=$(rcli "$1" config get maxmemory-policy | tail -n 1)
  echo "appendonly=$aof maxmemory-policy=$pol"; [ "$aof" = yes ] && [ "$pol" = noeviction ]
}
redis_persists() {
  local v='{"M1":0.6,"M2":0.5,"M3":0.7}' got
  rcli "$1" set iw:settings:thresholds "$v" >/dev/null
  dc "$1" restart redis >/dev/null 2>&1 && dc "$1" up -d --wait --wait-timeout 60 redis >/dev/null 2>&1
  got=$(rcli "$1" get iw:settings:thresholds); echo "after restart: $got"; [ "$got" = "$v" ]
}
only_on_data() { # only_on_data <project> <service>
  local nets; nets=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$(dc "$1" ps -q "$2")")
  echo "$2 networks: $nets"; [ "$nets" = "$1_data " ]
}

group_redis() {
  local p="iw-smoke-r-$RUN_ID"
  check "missing REDIS_PASSWORD is named" requires_secret REDIS_PASSWORD
  check "redis starts healthy" up "$p" 18445 18082 redis
  check "authenticated PING is PONG, unauthenticated is NOAUTH" redis_auth "$p"
  check "AOF on and noeviction" redis_config "$p"
  check "iw:settings:thresholds survives a restart" redis_persists "$p"
  check "redis is only on the internal data network" only_on_data "$p" redis
}

envval() { grep -E "^$2=" "$TMP/$1.env" | cut -d= -f2-; } # envval <project> <VAR>
minio_image() { dc "$1" config --images 2>/dev/null | grep -m1 minio; }
# mcp <project> <alias-url> <mc args...>: mc from the minio image, in a throwaway container on the data network.
mcp() {
  local p=$1 url=$2; shift 2
  docker run --rm -i --network "${p}_data" -e MC_CONFIG_DIR=/tmp/mc -e "MC_HOST_t=$url" \
    --entrypoint mc "$(minio_image "$p")" "$@"
}
app_url() { echo "http://$(envval "$1" MINIO_ACCESS_KEY):$(envval "$1" MINIO_SECRET_KEY)@minio:9000"; }
root_url() { echo "http://$(envval "$1" MINIO_ROOT_USER):$(envval "$1" MINIO_ROOT_PASSWORD)@minio:9000"; }
init_exited_ok() {
  local c code; c=$(dc "$1" ps -aq minio-init); [ -n "$c" ] || { echo "no minio-init container"; return 1; }
  code=$(docker inspect -f '{{.State.Status}} {{.State.ExitCode}}' "$c"); echo "minio-init: $code"; [ "$code" = "exited 0" ]
}
bucket_exists() { mcp "$1" "$(root_url "$1")" ls t/ | grep -q ' iw-raw/'; }
OBJ="html/00000000-0000-4000-8000-000000000001.html"
app_scoped() {
  local p=$1 u; u=$(app_url "$p")
  echo '<html>smoke</html>' | mcp "$p" "$u" pipe "t/iw-raw/$OBJ" >/dev/null || { echo "app put failed"; return 1; }
  [ "$(mcp "$p" "$u" cat "t/iw-raw/$OBJ")" = '<html>smoke</html>' ] || { echo "app get failed"; return 1; }
  echo tmp | mcp "$p" "$u" pipe t/iw-raw/tmp/del.txt >/dev/null && mcp "$p" "$u" rm t/iw-raw/tmp/del.txt >/dev/null \
    || { echo "app delete failed"; return 1; }
  mcp "$p" "$u" ls t/iw-raw/html/ >/dev/null || { echo "app list failed"; return 1; }
  if mcp "$p" "$u" mb t/iw-other >/dev/null 2>&1; then echo "app could create a bucket"; return 1; fi
  if mcp "$p" "$u" admin user list t >/dev/null 2>&1; then echo "app has admin rights"; return 1; fi
}
anonymous_denied() {
  local code; code=$(probe "$1_data" sh -c "wget -S -q -O /dev/null http://minio:9000/iw-raw/$OBJ 2>&1 | awk '/HTTP\\//{print \$2; exit}'")
  echo "anonymous GET: $code"; [ "$code" = 403 ]
}
init_idempotent() {
  local p=$1; dc "$p" up -d --force-recreate --no-deps minio-init >/dev/null 2>&1
  dc "$p" wait minio-init >/dev/null 2>&1 || true
  init_exited_ok "$p" && [ "$(mcp "$p" "$(app_url "$p")" cat "t/iw-raw/$OBJ")" = '<html>smoke</html>' ]
}

group_minio() {
  local p="iw-smoke-m-$RUN_ID"
  check "missing MINIO_ROOT_PASSWORD is named" requires_secret MINIO_ROOT_PASSWORD
  check "missing MINIO_SECRET_KEY is named" requires_secret MINIO_SECRET_KEY
  check "minio starts healthy and minio-init completes" up "$p" 18446 18083 minio minio-init
  dc "$p" wait minio-init >/dev/null 2>&1 || true
  check "minio-init exits 0" init_exited_ok "$p"
  check "bucket iw-raw exists" bucket_exists "$p"
  check "app credentials: read, write, delete, list on iw-raw only, no new bucket, no admin" app_scoped "$p"
  check "anonymous GET is denied" anonymous_denied "$p"
  check "minio-init is idempotent and keeps objects" init_idempotent "$p"
  check "minio is only on the internal data network" only_on_data "$p" minio
}

# ---------------------------------------------------------------- main

GROUPS_ALL=(parallel env redis minio)
[ $# -gt 0 ] && SELECTED=("$@") || SELECTED=("${GROUPS_ALL[@]}")
docker image inspect "$PROBE_IMAGE" >/dev/null 2>&1 || docker pull -q "$PROBE_IMAGE" >/dev/null
for g in "${SELECTED[@]}"; do log "== $g"; "group_$g"; done
log "smoke: $PASSES passed, $FAILS failed"
[ "$FAILS" -eq 0 ]
