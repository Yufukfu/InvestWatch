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

export function pinViolations(text) {
  const out = [];
  text.split('\n').forEach((raw, i) => {
    const line = raw.replace(/\s+#.*$/, '');
    const n = i + 1;
    const uses = line.match(/^\s*-?\s*uses:\s*(\S+)/);
    if (uses && !/@[0-9a-f]{40}$/.test(uses[1])) out.push(`line ${n}: action not pinned by commit SHA: ${uses[1]}`);
    if (/\bdocker\s+run\b/.test(line) || /^\s*IMAGE_[A-Z_]*:/.test(line)) {
      // An image reference: registry/name[:tag][@sha256:...], not inside a path or after a variable or mount colon.
      const images = line.matchAll(/(?<![\w:/.$@-])([a-z0-9][a-z0-9.-]*(?:\/[a-z0-9][a-z0-9._-]*)+(?::[\w.-]+)?(?:@sha256:[0-9a-f]+)?)/g);
      for (const [, image] of images)
        if (!/@sha256:[0-9a-f]{64}$/.test(image)) out.push(`line ${n}: image not pinned by digest: ${image}`);
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
