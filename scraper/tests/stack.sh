#!/usr/bin/env bash
# Stack check for the scraper deployment (spec openspec/specs/scraper-deployment).
# Runs against a throwaway compose project with its own env file and no host ports and removes it (containers,
# networks, volumes) on exit. Needs bash, Docker, Node (reads `docker compose config --format json`) and network
# (the image build downloads the pinned tls-client). It proves wiring, not a fetch: the production address guard
# refuses a stub on a compose address (design decision 9).
#
#   scraper/tests/stack.sh                run every group
#   scraper/tests/stack.sh config run     selected groups: config (no containers), root, run
#   STACK_ROOT=1 scraper/tests/stack.sh run   the same scenarios through the root compose.yaml
set -euo pipefail
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PROBE_IMAGE=public.ecr.aws/docker/library/alpine:3.22
TMP=$(mktemp -d)
RUN_ID="$$"
PROJECT="iw-stack-$RUN_ID"
HEALTH_PORT=18099  # not the default 8080, so "refused on the host" cannot hit the gateway or another service
FILES=(-f "$ROOT/infra/compose.yaml" -f "$ROOT/api/compose.yaml" -f "$ROOT/scraper/compose.yaml")
[ -z "${STACK_ROOT:-}" ] || FILES=(-f "$ROOT/compose.yaml")  # STACK_ROOT=1: run through the root file, as `docker compose up` does
ENVF="$TMP/stack.env"
FAILS=0
PASSES=0

log() { printf '%s\n' "$*" >&2; }
pass() { PASSES=$((PASSES + 1)); log "PASS  $*"; }
fail() { FAILS=$((FAILS + 1)); log "FAIL  $*"; }
check() { # check "<name>" cmd...  (passes when cmd exits 0)
  local name=$1; shift
  if "$@" >"$TMP/last.out" 2>&1; then pass "$name"; else fail "$name"; sed 's/^/      /' "$TMP/last.out" | tail -n 15 >&2; fi
}
sedi() { local f=${!#} n=$(($# - 1)); sed "${@:1:n}" "$f" >"$f.sedi" && mv "$f.sedi" "$f"; }

dc() { docker compose -p "$PROJECT" --env-file "$ENVF" "${FILES[@]}" "$@"; }
cleanup() {
  dc down -v --remove-orphans >/dev/null 2>&1 || true
  docker compose -p "$PROJECT-fail" --env-file "$ENVF" "${FILES[@]}" -f "$TMP/seed-fails.yaml" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

# Env file from .env.example with random secrets, this project's name and a fixed health port.
"$ROOT/scripts/init-env.sh" "$ENVF" >/dev/null
sedi -e "s|^COMPOSE_PROJECT_NAME=.*|COMPOSE_PROJECT_NAME=$PROJECT|" "$ENVF"
printf 'SCRAPER_HEALTH_PORT=%s\n' "$HEALTH_PORT" >>"$ENVF"
envval() { grep -E "^$1=" "$ENVF" | cut -d= -f2-; }

# ------------------------------------------------------------ config group (no containers)

cfg() { dc config --format json >"$TMP/cfg.json"; }
# js <body>: runs JS with `c` (the compose model) and `e` (the env file values); throwing fails the check.
js() {
  local envjson
  envjson=$(node -e '
    const out = {};
    for (const l of require("fs").readFileSync(process.argv[1], "utf8").split("\n")) {
      const m = l.match(/^([A-Z0-9_]+)=(.*)$/); if (m) out[m[1]] = m[2];
    }
    console.log(JSON.stringify(out));' "$ENVF")
  node -e '
    const c = require(process.argv[1]);
    const e = JSON.parse(process.argv[2]);
    const S = ["worker", "scheduler", "seed"];
    const fail = (m) => { throw new Error(m); };
    '"$1" "$TMP/cfg.json" "$envjson"
}

services_exist() { js 'for (const s of S) if (!c.services[s]) fail("missing service " + s)'; }
gates_declared() {
  js '
    const need = (svc, dep, cond) => {
      const d = (c.services[svc].depends_on || {})[dep];
      if (!d || d.condition !== cond) fail(svc + " must depend on " + dep + " with " + cond);
    };
    for (const s of ["worker", "scheduler"]) {
      for (const d of ["api-migrate", "seed", "minio-init"]) need(s, d, "service_completed_successfully");
      for (const d of ["postgres", "redis"]) need(s, d, "service_healthy");
    }
    need("seed", "api-migrate", "service_completed_successfully");
    need("seed", "postgres", "service_healthy");'
}
restart_policies() {
  js '
    for (const s of ["worker", "scheduler"]) if (c.services[s].restart !== "unless-stopped") fail(s + " restart " + c.services[s].restart);
    if (c.services.seed.restart !== "no") fail("seed restart " + c.services.seed.restart)'
}
image_built_once() { # three builds of one tag race on the containerd image store: only worker may build
  js '
    const builders = ["seed", "worker", "scheduler"].filter((n) => c.services[n].build);
    if (builders.join() !== "worker") fail("services that build the image: " + builders.join(",") + " (want worker only)")
    const tags = new Set(["seed", "worker", "scheduler"].map((n) => c.services[n].image));
    if (tags.size !== 1) fail("the roles use different images: " + [...tags].join(","))'
}
single_scheduler() {
  js '
    const s = c.services.scheduler;
    if (s.container_name) fail("scheduler has container_name");
    const r = s.deploy && s.deploy.replicas;
    if (r !== undefined && r > 1) fail("scheduler replicas " + r)'
}
secrets_have_no_default() { # structural: infra and api fail on the same unset variables first, so read the file
  local f="$ROOT/scraper/compose.yaml" v
  for v in POSTGRES_APP_PASSWORD REDIS_PASSWORD MINIO_SECRET_KEY; do
    local all required
    all=$(grep -Eo "\\$\\{$v[:}-]" "$f" | wc -l | tr -d ' '); required=$(grep -Eo "\\$\\{$v:\\?" "$f" | wc -l | tr -d ' ')
    [ "$required" -ge 1 ] && [ "$all" = "$required" ] || { echo "$v: $required of $all uses are the required form"; return 1; }
  done
}
no_admin_credential() {
  js '
    const banned = [e.POSTGRES_ADMIN_PASSWORD, e.MINIO_ROOT_PASSWORD, e.POSTGRES_ADMIN_USER, e.MINIO_ROOT_USER];
    if (banned.some((b) => !b)) fail("an admin value is unset in the env file, the check would be vacuous");
    for (const s of S) for (const [k, v] of Object.entries(c.services[s].environment || {})) {
      for (const b of banned) if (String(v).includes(b)) fail(s + "." + k + " holds an admin credential");
    }
    for (const s of S) {
      const u = (c.services[s].environment || {}).DATABASE_URL || "";
      if (!u.startsWith("postgresql://" + e.POSTGRES_APP_USER + ":")) fail(s + " DATABASE_URL is not the app role");
    }'
}
seed_holds_less() {
  js '
    const keys = Object.keys(c.services.seed.environment || {});
    const extra = keys.filter((k) => k === "REDIS_URL" || k.startsWith("MINIO_"));
    if (extra.length) fail("seed has " + extra.join(","));
    if (!keys.includes("DATABASE_URL")) fail("seed has no DATABASE_URL")'
}
networks_and_ports() {
  js '
    for (const s of S) {
      const n = Object.keys(c.services[s].networks || {});
      if (!n.length || n.some((x) => x !== "data" && x !== "egress")) fail(s + " networks " + n);
      if ((c.services[s].ports || []).length) fail(s + " publishes a port");
    }
    if (!Object.keys(c.services.worker.networks).includes("egress")) fail("worker has no route out")
    for (const s of ["scheduler", "seed"]) {
      const n = Object.keys(c.services[s].networks).join(",");
      if (n !== "data") fail(s + " fetches nothing and must be on data alone, not " + n);
    }'
}
hardening_declared() {
  js '
    for (const s of S) {
      const v = c.services[s];
      if (v.read_only !== true) fail(s + " not read_only");
      if (!(v.cap_drop || []).includes("ALL")) fail(s + " cap_drop");
      if (!(v.security_opt || []).includes("no-new-privileges:true")) fail(s + " no-new-privileges");
      if (!(v.tmpfs || []).some((t) => t === "/tmp" || t.startsWith("/tmp:"))) fail(s + " tmpfs /tmp");
      const l = v.deploy && v.deploy.resources && v.deploy.resources.limits;
      if (!l || !Number(l.cpus) || !Number(l.memory)) fail(s + " limits " + JSON.stringify(l));
    }'
}
grace_covers_deadline() {
  js '
    const unit = { h: 3600, m: 60, s: 1 };
    const parse = (t) => [...String(t).matchAll(/([\d.]+)([hms])/g)].reduce((a, m) => a + Number(m[1]) * unit[m[2]], 0);
    const deadline = Number((c.services.worker.environment || {}).SCRAPER_SHUTDOWN_DEADLINE);
    if (!(deadline > 0)) fail("worker has no SCRAPER_SHUTDOWN_DEADLINE");
    const grace = parse(c.services.worker.stop_grace_period);
    if (grace < deadline + 20) fail("grace " + grace + "s < deadline " + deadline + "s + 20s")'
}
seed_cron_argument() { # the default, then an override passed through to the command line
  js 'const cmd = c.services.seed.command; if (cmd[cmd.length - 1] !== "0 */6 * * *") fail("default cron " + JSON.stringify(cmd))' || return 1
  SCRAPER_SEED_CRON='*/7 * * * *' cfg
  js 'const cmd = c.services.seed.command; if (cmd[cmd.length - 1] !== "*/7 * * * *") fail("override cron " + JSON.stringify(cmd))'
  local rc=$?; cfg; return $rc
}

group_config() {
  check "scraper/compose.yaml exists and the model builds" cfg
  [ -s "$TMP/cfg.json" ] || return 0  # nothing to inspect: the checks below would only repeat this failure
  check "worker, scheduler and seed are defined" services_exist
  check "start order gates are declared" gates_declared
  check "restart policies" restart_policies
  check "scheduler is defined once" single_scheduler
  check "one image, built by worker only" image_built_once
  check "secrets have no default" secrets_have_no_default
  check "no admin credential, app role in DATABASE_URL" no_admin_credential
  check "seed holds the database URL only" seed_holds_less
  check "networks are data and egress, no published port" networks_and_ports
  check "hardening is declared with limits" hardening_declared
  check "stop grace covers the shutdown deadline" grace_covers_deadline
  check "seed passes the cron argument" seed_cron_argument
}

# ------------------------------------------------------------ run group (containers)

cid() { dc ps -a -q "$1" | head -n1; }
inspect() { docker inspect -f "$2" "$(cid "$1")"; }
knf_rows() { # prints "<count>|<schedule_cron>"
  dc exec -T postgres psql -U "$(envval POSTGRES_ADMIN_USER)" -d "$(envval POSTGRES_DB)" -tAc \
    "select count(*) || '|' || coalesce(max(schedule_cron), '') from sources where url = 'https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne'"
}

invalid_cron_refused() {
  dc build worker >/dev/null || return 1  # never judge a stale image tagged by an earlier run
  dc up -d --wait api-migrate minio-init || return 1
  local out
  if out=$(SCRAPER_SEED_CRON='not a cron' dc run --rm --no-deps seed 2>&1); then echo "seed accepted an invalid cron"; return 1; fi
  case $out in *"invalid cron"*) ;; *) echo "failed for another reason: $out"; return 1 ;; esac
  [ "$(knf_rows)" = "0|" ] || { echo "a row was written: $(knf_rows)"; return 1; }
}
seed_failure_blocks_services() {
  cat >"$TMP/seed-fails.yaml" <<'YAML'
services:
  seed:
    command: ["python", "-c", "raise SystemExit(1)"]
YAML
  local p="$PROJECT-fail"
  if docker compose -p "$p" --env-file "$ENVF" "${FILES[@]}" -f "$TMP/seed-fails.yaml" up -d --wait worker scheduler; then
    echo "stack started with a failing seed"; return 1
  fi
  # Compose may create the dependents, but it must never start them: "created" with no start time.
  local id state
  for id in $(docker compose -p "$p" --env-file "$ENVF" "${FILES[@]}" -f "$TMP/seed-fails.yaml" ps -a -q worker scheduler); do
    state=$(docker inspect -f '{{.State.Status}} {{.State.StartedAt}}' "$id")
    [ "$state" = "created 0001-01-01T00:00:00Z" ] || { echo "a dependent was started: $state"; return 1; }
  done
  docker compose -p "$p" --env-file "$ENVF" "${FILES[@]}" -f "$TMP/seed-fails.yaml" down -v --remove-orphans >/dev/null 2>&1
}
stack_starts() {
  dc up -d --build --wait --wait-timeout 240 worker scheduler || return 1
  sleep 15  # settle: a crash loop shows as RestartCount > 0
  [ "$(inspect seed '{{.State.ExitCode}}')" = 0 ] || { echo "seed exit $(inspect seed '{{.State.ExitCode}}')"; return 1; }
  [ "$(inspect worker '{{.State.Health.Status}}')" = healthy ] || { echo "worker $(inspect worker '{{.State.Health.Status}}')"; return 1; }
  [ "$(inspect scheduler '{{.State.Running}} {{.RestartCount}}')" = "true 0" ] || { echo "scheduler $(inspect scheduler '{{.State.Running}} {{.RestartCount}}')"; return 1; }
}
cron_stored_and_valid() {
  local row count cron; row=$(knf_rows); count=${row%%|*}; cron=${row#*|}
  [ "$count" = 1 ] && [ -n "$cron" ] || { echo "row: $row"; return 1; }
  dc run --rm --no-deps -T worker python -c 'import sys; from croniter import croniter; sys.exit(0 if croniter.is_valid(sys.argv[1]) else 1)' "$cron"
}
seed_rerun_keeps_one_row() {
  dc down >/dev/null 2>&1 || true  # containers and networks go, volumes stay
  dc up -d --wait --wait-timeout 240 worker scheduler || return 1
  [ "$(inspect seed '{{.State.ExitCode}}')" = 0 ] && [ "$(knf_rows | cut -d'|' -f1)" = 1 ] || { echo "rows: $(knf_rows)"; return 1; }
}
no_port_published_not_on_edge() {
  local s ports nets
  for s in worker scheduler seed; do
    ports=$(inspect "$s" '{{json .NetworkSettings.Ports}}'); nets=$(inspect "$s" '{{range $k, $_ := .NetworkSettings.Networks}}{{$k}} {{end}}')
    case $ports in "{}"|null) ;; *) echo "$s publishes $ports"; return 1 ;; esac
    case $nets in *_edge*) echo "$s is on edge: $nets"; return 1 ;; esac
  done
}
health_internal_only() {
  docker run --rm --network "${PROJECT}_data" "$PROBE_IMAGE" wget -q -O- "http://worker:$HEALTH_PORT/health" >/dev/null || { echo "no 200 from data"; return 1; }
  if curl -s -o /dev/null --max-time 3 "http://127.0.0.1:$HEALTH_PORT/health"; then echo "answered on the host"; return 1; fi
}
hardening_running() {
  local s out user ro caps sec tmp cpus mem
  for s in worker scheduler seed; do
    out=$(inspect "$s" '{{.Config.User}}|{{.HostConfig.ReadonlyRootfs}}|{{json .HostConfig.CapDrop}}|{{json .HostConfig.SecurityOpt}}|{{json .HostConfig.Tmpfs}}|{{.HostConfig.NanoCpus}}|{{.HostConfig.Memory}}')
    echo "$s $out"
    IFS='|' read -r user ro caps sec tmp cpus mem <<<"$out"
    case $user in ""|root|0) echo "$s runs as root"; return 1 ;; esac
    [ "$ro" = true ] && [[ $caps == *ALL* ]] && [[ $sec == *no-new-privileges* ]] && [[ $tmp == */tmp* ]] \
      && [ "$cpus" -gt 0 ] && [ "$mem" -gt 0 ] || { echo "$s is not hardened"; return 1; }
  done
}
write_outside_tmp_refused() {
  local out
  if out=$(dc exec -T worker python -c 'open("/app/x", "w")' 2>&1); then echo "write succeeded"; return 1; fi
  case $out in *"Read-only file system"*) ;; *) echo "$out"; return 1 ;; esac
  dc exec -T worker python -c 'import tempfile; tempfile.NamedTemporaryFile().close()'  # /tmp stays writable
}
idle_stop_is_clean() {
  local start end; start=$(date +%s)
  dc stop worker >/dev/null || return 1
  end=$(date +%s)
  [ "$(inspect worker '{{.State.ExitCode}}')" = 0 ] && [ $((end - start)) -lt 20 ] || { echo "exit $(inspect worker '{{.State.ExitCode}}') after $((end - start))s"; return 1; }
}

group_run() {
  check "an invalid seed cron exits non-zero and writes no row" invalid_cron_refused
  check "a failing seed keeps worker and scheduler from being created" seed_failure_blocks_services
  check "stack starts: seed 0, worker healthy, scheduler running without restarts" stack_starts
  check "seeded source has a valid cron" cron_stored_and_valid
  check "no scraper container publishes a port or is on edge" no_port_published_not_on_edge
  check "worker health answers inside data and not on the host" health_internal_only
  check "running containers are non-root, read-only, capless, limited" hardening_running
  check "a write outside /tmp is refused" write_outside_tmp_refused
  check "a second start reruns seed and keeps one source row" seed_rerun_keeps_one_row
  check "stopping an idle worker exits 0 before the grace period" idle_stop_is_clean
}

# ------------------------------------------------------------ root group (root compose.yaml)

root_lists_scraper() {
  docker compose --env-file "$ENVF" -f "$ROOT/compose.yaml" config --services >"$TMP/root-services.txt" || return 1
  local s; for s in worker scheduler seed; do grep -qx "$s" "$TMP/root-services.txt" || { echo "root compose has no $s"; return 1; }; done
}

group_root() {
  check "the root compose.yaml lists worker, scheduler and seed" root_lists_scraper
}

groups=("$@")
[ ${#groups[@]} -gt 0 ] || groups=(config root run)
for g in "${groups[@]}"; do "group_$g"; done

log ""
log "$PASSES passed, $FAILS failed"
[ "$FAILS" -eq 0 ]
