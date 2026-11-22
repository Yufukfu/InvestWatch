// Pin rules for the security workflow (ADR 0209 decision 5, openspec change security-ci):
// every action by full commit SHA, every docker image by digest, every pip-installed scanner by exact version.
// Text checks only, so the test needs no YAML parser and runs in under a second.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const WORKFLOW = join(dirname(fileURLToPath(import.meta.url)), '..', 'workflows', 'security.yml');
const SCANNERS = ['pip-audit'];
const DIGEST_RE = /@sha256:[0-9a-f]{64}$/;
// `docker run` options that take a value as the next word. A word after an unknown option cannot be told apart
// from the image, so an unknown option is reported (fail closed) and gets added here once it is reviewed.
const VALUE_OPTS = new Set(['-v', '--volume', '-e', '--env', '--env-file', '-w', '--workdir', '--name', '-p', '--publish',
  '--network', '--mount', '-u', '--user', '--platform', '--entrypoint', '--pull', '-l', '--label', '--tmpfs']);
const FLAG_OPTS = new Set(['--rm', '-d', '--detach', '-i', '--interactive', '-t', '--tty', '-it', '-ti', '--init', '--read-only']);

// Shell words of one line, with quotes removed. Enough for workflow `run:` lines, not a full shell parser.
function words(s) {
  return [...s.matchAll(/"([^"]*)"|'([^']*)'|(\S+)/g)].map((m) => m[1] ?? m[2] ?? m[3]);
}

// The image of `docker run ...`: the first word that is not an option or an option's value.
function dockerRunImage(args) {
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (!a.startsWith('-')) return { image: a };
    if (a.startsWith('--') && a.includes('=')) continue;
    if (FLAG_OPTS.has(a)) continue;
    if (VALUE_OPTS.has(a)) { i++; continue; }
    return { error: `unknown docker run option ${a}` };
  }
  return { error: 'docker run without an image' };
}

export function pinViolations(text) {
  const out = [];
  const lines = text.split('\n');
  lines.forEach((raw, i) => {
    let line = raw.replace(/\s+#.*$/, '');
    const n = i + 1;
    const uses = line.match(/^\s*-?\s*uses:\s*(\S+)/);
    if (uses && !/@[0-9a-f]{40}$/.test(uses[1])) out.push(`line ${n}: action not pinned by commit SHA: ${uses[1]}`);
    const unpinned = (image) => out.push(`line ${n}: image not pinned by digest: ${image}`);
    // Image values: an IMAGE_* env, a job `container:` or a service `image:` (a `container:` mapping has no value here,
    // its nested `image:` is checked on its own line), and IMAGE_* set in shell, including through $GITHUB_ENV.
    const key = line.match(/^\s*-?\s*(IMAGE_[A-Z0-9_]*|image|container):\s*["']?([^\s"']+)/);
    if (key && !DIGEST_RE.test(key[2])) unpinned(key[2]);
    for (const [, value] of line.matchAll(/\bIMAGE_[A-Z0-9_]*=["']?([^\s"']+)/g)) if (!DIGEST_RE.test(value)) unpinned(value);
    if (/\bdocker\s+run\b/.test(line)) {
      // A command continued with a trailing backslash is read up to its last line.
      for (let j = i + 1; /\\\s*$/.test(line) && j < lines.length; j++) line = line.replace(/\\\s*$/, ' ') + lines[j].replace(/\s+#.*$/, '');
      // Every `docker run` on the line, also chained ones (`a && docker run ...`).
      for (const segment of line.split(/\bdocker\s+run\b/).slice(1)) {
        const run = dockerRunImage(words(segment));
        if (run.error) out.push(`line ${n}: ${run.error}`);
        // A variable image is allowed only as an IMAGE_* variable, whose value the checks above pin.
        else if (!/^\$\{?IMAGE_[A-Z0-9_]*\}?$/.test(run.image) && !DIGEST_RE.test(run.image)) unpinned(run.image);
      }
    }
    const pip = line.match(/\bpip\s+install\b(.*)$/);
    if (pip) {
      for (const tool of SCANNERS) {
        const m = pip[1].match(new RegExp(`(?:^|\\s)${tool}(\\S*)`));
        if (m && !/^==[0-9][\w.]*$/.test(m[1])) out.push(`line ${n}: ${tool} not pinned to an exact version`);
      }
    }
  });
  return out;
}

const SHA = 'a'.repeat(40);
const DIGEST = 'b'.repeat(64);
const PINNED = [
  `      - uses: actions/checkout@${SHA} # v4.3.1`,
  `      IMAGE_GITLEAKS: zricethezav/gitleaks:v8.28.0@sha256:${DIGEST}`,
  `          docker run --rm -v "$PWD:/repo:ro" ghcr.io/google/osv-scanner:v2.2.4@sha256:${DIGEST} scan source -r /repo`,
  `          docker run --rm -v "$PWD:/repo:ro" "$IMAGE_GITLEAKS" git /repo --redact`,
  `          docker run --rm -v osv-db:/root/.cache/osv-scanner -v "$PWD:/src:ro" "$IMAGE_OSV" scan source -r /src`,
  '          pip install pip-audit==2.10.1',
].join('\n');

test('a fully pinned workflow passes', () => {
  assert.deepEqual(pinViolations(PINNED), []);
});

test('an action pinned by tag only fails and names the line', () => {
  const v = pinViolations(PINNED.replace(`@${SHA}`, '@v4'));
  assert.equal(v.length, 1);
  assert.match(v[0], /^line 1: action not pinned by commit SHA: actions\/checkout@v4$/);
});

test('a docker run image without a digest fails and names the image', () => {
  const v = pinViolations(PINNED.replace(`:v2.2.4@sha256:${DIGEST}`, ':v2.2.4'));
  assert.equal(v.length, 1);
  assert.match(v[0], /^line 3: image not pinned by digest: ghcr\.io\/google\/osv-scanner:v2\.2\.4$/);
});

test('an image after a volume mount without a digest fails', () => {
  const v = pinViolations(PINNED.replace('"$IMAGE_OSV"', 'ghcr.io/google/osv-scanner:v2.2.4'));
  assert.equal(v.length, 1);
  assert.match(v[0], /^line 5: image not pinned by digest: ghcr\.io\/google\/osv-scanner:v2\.2\.4$/);
});

test('an image variable without a digest fails', () => {
  const v = pinViolations(PINNED.replace(`:v8.28.0@sha256:${DIGEST}`, ':v8.28.0'));
  assert.equal(v.length, 1);
  assert.match(v[0], /^line 2: image not pinned by digest: zricethezav\/gitleaks:v8\.28\.0$/);
});

test('a Docker Hub image without a slash and without a digest fails', () => {
  for (const [bad, image] of [['docker run --rm alpine:3.20 sh', 'alpine:3.20'], ['docker run --rm -w /src node:22 npm audit', 'node:22'], ['docker run busybox', 'busybox']]) {
    const v = pinViolations(PINNED.replace(`docker run --rm -v "$PWD:/repo:ro" "$IMAGE_GITLEAKS" git /repo --redact`, bad));
    assert.deepEqual(v, [`line 4: image not pinned by digest: ${image}`], bad);
  }
});

test('an image variable whose name has a digit is checked', () => {
  const v = pinViolations(`${PINNED}\n      IMAGE_OSV2: ghcr.io/google/osv-scanner:v2.2.4`);
  assert.deepEqual(v, ['line 7: image not pinned by digest: ghcr.io/google/osv-scanner:v2.2.4']);
});

test('a variable image that is not an IMAGE_* env fails', () => {
  const v = pinViolations(PINNED.replace('"$IMAGE_GITLEAKS"', '"$SCANNER"'));
  assert.deepEqual(v, ['line 4: image not pinned by digest: $SCANNER']);
});

test('an unknown docker run option fails closed instead of guessing the image', () => {
  const v = pinViolations(PINNED.replace('docker run --rm -v "$PWD:/repo:ro"', 'docker run --rm --cap-add NET_ADMIN'));
  assert.deepEqual(v, ['line 3: unknown docker run option --cap-add']);
});

test('the image of a docker run continued over several lines is checked', () => {
  const v = pinViolations(`${PINNED}\n          docker run --rm \\\n            -v "$PWD:/src:ro" \\\n            node:22 npm audit`);
  assert.deepEqual(v, ['line 7: image not pinned by digest: node:22']);
});

test('every docker run on a chained line is checked', () => {
  for (const sep of ['&&', ';', '|', '||']) {
    const v = pinViolations(`${PINNED}\n          docker run --rm "$IMAGE_OSV" scan ${sep} docker run alpine:3.20 echo`);
    assert.deepEqual(v, ['line 7: image not pinned by digest: alpine:3.20'], sep);
  }
});

test('job container and service images are checked', () => {
  for (const [yaml, line] of [['    container: alpine:3.20', 7], ['    container:\n      image: "node:22"', 8], ['      postgres:\n        image: postgres:17-alpine', 8]]) {
    const v = pinViolations(`${PINNED}\n${yaml}`);
    assert.equal(v.length, 1, yaml);
    assert.match(v[0], new RegExp(`^line ${line}: image not pinned by digest: `), yaml);
  }
  assert.deepEqual(pinViolations(`${PINNED}\n    container:\n      image: alpine:3.20@sha256:${DIGEST}`), []);
});

test('an IMAGE_* set in shell or through GITHUB_ENV is checked', () => {
  for (const bad of ['          IMAGE_X=alpine:3.20 docker run "$IMAGE_X"', '          echo "IMAGE_X=node:22" >> "$GITHUB_ENV"']) {
    const v = pinViolations(`${PINNED}\n${bad}`);
    assert.equal(v.length, 1, bad);
    assert.match(v[0], /^line 7: image not pinned by digest: (alpine:3\.20|node:22)$/, bad);
  }
  assert.deepEqual(pinViolations(`${PINNED}\n          IMAGE_X=alpine:3.20@sha256:${DIGEST} docker run "$IMAGE_X"`), []);
});

test('an unpinned or range-pinned scanner package fails', () => {
  for (const bad of ['pip install pip-audit', 'pip install pip-audit>=2.10', 'pip install pytest pip-audit']) {
    const v = pinViolations(PINNED.replace('pip install pip-audit==2.10.1', bad));
    assert.equal(v.length, 1, bad);
    assert.match(v[0], /^line 6: pip-audit not pinned to an exact version$/);
  }
});

test('the real security workflow exists and is fully pinned', () => {
  assert.ok(existsSync(WORKFLOW), `${WORKFLOW} is missing`);
  const text = readFileSync(WORKFLOW, 'utf8');
  assert.match(text, /^\s*-?\s*uses:/m, 'the workflow uses no action at all, so the check proves nothing');
  assert.match(text, /docker run/, 'the workflow runs no image, so the digest check proves nothing');
  assert.deepEqual(pinViolations(text), []);
});
