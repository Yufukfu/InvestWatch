'use strict';
// Claude Code evaluates permission rules deny, then ask, then allow, and the first match decides:
// a matching `ask` rule prompts even when a more specific `allow` rule also matches
// (https://code.claude.com/docs/en/permissions). So an `ask` rule that is a prefix of an `allow` rule
// silently cancels it. PR 27 shipped exactly that: `ask: Bash(git push:*)` over `allow: Bash(git push origin:*)`.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const settings = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'settings.json'), 'utf8'));
const { allow = [], ask = [], deny = [] } = settings.permissions || {};

// `Bash(git push origin:*)` -> { tool: 'Bash', prefix: 'git push origin' }; a rule without `:*` is exact.
function parse(rule) {
  const m = /^(\w+)\((.*)\)$/.exec(rule);
  if (!m) return { tool: rule, prefix: '', exact: true };
  const wildcard = m[2].endsWith(':*');
  return { tool: m[1], prefix: wildcard ? m[2].slice(0, -2) : m[2], exact: !wildcard };
}

// Does `broad` match every command that `narrow` matches?
function covers(broad, narrow) {
  const [b, n] = [parse(broad), parse(narrow)];
  if (b.tool !== n.tool) return false;
  if (b.exact) return n.exact && n.prefix === b.prefix;
  return n.prefix === b.prefix || n.prefix.startsWith(`${b.prefix} `);
}

test('no ask or deny rule covers an allow rule, which would silently cancel it', () => {
  for (const a of allow) {
    for (const other of [...ask.map((r) => ['ask', r]), ...deny.map((r) => ['deny', r])]) {
      assert.equal(covers(other[1], a), false, `${other[0]} rule ${other[1]} covers allow rule ${a}, so ${a} never applies`);
    }
  }
});

test('the push and PR rules of ADR 0207 are the ones in settings.json', () => {
  assert.ok(allow.includes('Bash(git push origin:*)'));
  assert.ok(allow.includes('Bash(git push -u origin:*)'));
  assert.ok(allow.includes('Bash(gh pr create:*)'));
  for (const r of ['Bash(gh pr merge:*)', 'Bash(gh pr ready:*)', 'Bash(gh pr review:*)']) assert.ok(ask.includes(r), r);
  assert.ok(!allow.some((r) => /^Bash\(git push:\*\)$/.test(r)), 'a bare git push rule would allow any remote');
});
