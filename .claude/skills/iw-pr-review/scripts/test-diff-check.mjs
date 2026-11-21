#!/usr/bin/env node
// Deterministic check (no LLM) that a branch did not weaken the tests it inherited. Compares each test file
// at the MERGE-BASE with the base branch against the same file at the head (not the tip of origin/main, which
// moves on and would blame the branch for other people's commits), and flags:
//   deleted-test-file        a test file that existed at the merge-base is gone (or renamed to a non-test name)
//   added-skip               more skip / xfail / only / todo markers than before
//   net-removed-assertions   fewer assertions than before (commented-out ones do not count)
// Files are compared by content counts, so renames are followed and in-place rewrites are not flagged.
// A flag is a question for the author or reviewer ("explain it in the PR body"), not proof of a defect.
//
// "Test file" = pytest files (test_*.py, *_test.py, anything .py under tests/), JS/TS *.test.* / *.spec.*,
// and __tests__/. Counts are textual, so a parametrised test or a helper that hides asserts can still weaken
// coverage unnoticed; this check is a floor, not a coverage tool.
//
// Usage: node test-diff-check.mjs [--base REF] [--head REF] [--repo-root DIR] [--json]
//   --base defaults to origin/main; --head to HEAD.
// Exit 1 when anything is flagged, 2 on a bad ref or a flag without a value.

import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const TEST_FILE_RE = /(?:\.(?:test|spec)\.[cm]?[jt]sx?$)|(?:(?:^|\/)__tests__\/)|(?:(?:^|\/)test_[^/]*\.py$)|(?:_test\.py$)|(?:(?:^|\/)tests?\/.+\.py$)/;
const SKIP_RE = new RegExp(
  [
    String.raw`\b(?:it|test|describe)\.(?:skip|only|todo)\b`,
    String.raw`\b(?:xit|xdescribe|xtest|fit|fdescribe)\s*\(`,
    String.raw`@pytest\.mark\.(?:skip|skipif|xfail)\b`,
    String.raw`\bpytest\.(?:skip|xfail)\s*\(`,
    String.raw`@unittest\.(?:skip|skipIf|skipUnless|expectedFailure)\b`,
    String.raw`\bself\.skipTest\s*\(`,
  ].join('|'),
  'g',
);
// One alternation, one count per assertion: a line-leading `assert` statement is matched by its own branch, so
// `assert (x)` is not also counted by the call-style branch.
const ASSERTION_RE = new RegExp(
  [
    String.raw`\b(?:expect|assert)\w*(?:\.\w+)?\s*\(`,
    String.raw`^\s*assert\b`,
    String.raw`\bpytest\.raises\s*\(`,
    String.raw`\bself\.assert\w+\s*\(`,
  ].join('|'),
  'g',
);
const COMMENT_LINE_RE = /^\s*(?:\/\/|\/\*|\*|#)/;
// No leading '-' (would parse as a git option) and no '..' segments. ~ and ^ allow HEAD~1 and HEAD^.
const REF_RE = /^[A-Za-z0-9_][A-Za-z0-9._/~^-]*$/;

export const isTestFile = (file) => TEST_FILE_RE.test(file);

function git(root, args) {
  return execFileSync('git', args, { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: 64 * 1024 * 1024 });
}

function resolveRef(root, ref, label) {
  if (!REF_RE.test(ref) || ref.includes('..')) throw new Error(`unsafe ${label} ref "${ref}"`);
  try {
    return git(root, ['rev-parse', '--verify', '--quiet', `${ref}^{commit}`]).trim();
  } catch {
    throw new Error(`${label} ref "${ref}" does not exist (git fetch?)`);
  }
}

// `git diff --name-status -z -M`: "M\0path\0", "D\0path\0", "R087\0old\0new\0".
function changedFiles(root, from, to) {
  const parts = git(root, ['diff', '--name-status', '-z', '-M', '--no-color', '--no-ext-diff', '--no-textconv', from, to]).split('\0').filter(Boolean);
  const entries = [];
  for (let i = 0; i < parts.length;) {
    const code = parts[i++][0];
    if (code === 'R' || code === 'C') entries.push({ code, oldPath: parts[i++], path: parts[i++] });
    else entries.push({ code, path: parts[i++] });
  }
  return entries;
}

function countsAt(root, sha, file) {
  let text;
  try {
    text = git(root, ['show', `${sha}:${file}`]);
  } catch {
    return null;
  }
  const counts = { assertions: 0, skips: 0 };
  for (const line of text.split('\n')) {
    if (COMMENT_LINE_RE.test(line)) continue;
    counts.assertions += (line.match(ASSERTION_RE) ?? []).length;
    counts.skips += (line.match(SKIP_RE) ?? []).length;
  }
  return counts;
}

export function checkTestDiff({ repoRoot = process.cwd(), base = 'origin/main', head = 'HEAD' } = {}) {
  try {
    git(repoRoot, ['rev-parse', '--git-dir']);
  } catch {
    throw new Error(`repo root "${repoRoot}" is not a git repository`);
  }
  const baseSha = resolveRef(repoRoot, base, 'base');
  const headSha = resolveRef(repoRoot, head, 'head');
  const mergeBase = git(repoRoot, ['merge-base', baseSha, headSha]).trim();
  const flags = [];

  for (const { code, oldPath, path: file } of changedFiles(repoRoot, mergeBase, headSha)) {
    const before = oldPath ?? file;
    if (!isTestFile(before)) continue;
    if (code === 'D' || (code === 'R' && !isTestFile(file))) {
      flags.push({ kind: 'deleted-test-file', file: before, detail: code === 'D' ? 'test file deleted' : `renamed to ${file}, which is not a test file` });
      continue;
    }
    if (code !== 'M' && code !== 'R' && code !== 'T') continue;
    const was = countsAt(repoRoot, mergeBase, before);
    const now = countsAt(repoRoot, headSha, file);
    if (!was || !now) continue;
    if (now.skips > was.skips) flags.push({ kind: 'added-skip', file, detail: `skip/xfail/only/todo markers ${was.skips} -> ${now.skips}` });
    if (now.assertions < was.assertions) flags.push({ kind: 'net-removed-assertions', file, detail: `assertions ${was.assertions} -> ${now.assertions}` });
  }
  return flags;
}

function main(argv) {
  const args = argv.slice(2);
  const val = (name) => {
    const i = args.indexOf(name);
    if (i === -1) return undefined;
    const v = args[i + 1];
    if (v === undefined || v.startsWith('--')) throw new Error(`${name} needs a value`);
    return v;
  };
  let flags;
  try {
    flags = checkTestDiff({ repoRoot: val('--repo-root'), base: val('--base'), head: val('--head') });
  } catch (e) {
    process.stderr.write(`test-diff-check: ${e.message}\n`);
    process.exit(2);
  }
  if (args.includes('--json')) process.stdout.write(`${JSON.stringify(flags, null, 2)}\n`);
  else if (!flags.length) process.stdout.write('test-diff-check: no weakened tests\n');
  else for (const f of flags) process.stdout.write(`${f.kind.padEnd(22)} ${f.file}: ${f.detail}\n`);
  process.exit(flags.length ? 1 : 0);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) main(process.argv);
