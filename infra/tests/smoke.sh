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
  {
    printf 'COMPOSE_PROJECT_NAME=%s\nIW_HTTPS_PORT=%s\nIW_HTTP_PORT=%s\n' "$p" "$2" "$3"
  } >>"$f"
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

# ---------------------------------------------------------------- main

GROUPS_ALL=(parallel)
[ $# -gt 0 ] && SELECTED=("$@") || SELECTED=("${GROUPS_ALL[@]}")
docker image inspect "$PROBE_IMAGE" >/dev/null 2>&1 || docker pull -q "$PROBE_IMAGE" >/dev/null
for g in "${SELECTED[@]}"; do log "== $g"; "group_$g"; done
log "smoke: $PASSES passed, $FAILS failed"
[ "$FAILS" -eq 0 ]
