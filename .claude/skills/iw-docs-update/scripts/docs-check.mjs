#!/usr/bin/env node
// Deterministic docs check, no LLM, no network. Usage: node docs-check.mjs [repoRoot]
// Fails (exit 1) on: broken relative markdown links, backticked .md paths that do not
// exist, ADR files missing from .docs/decisions/README.md, service dirs without CLAUDE.md,
// service dirs without a .github/CODEOWNERS line, and a per-person ownership statement in a
// live doc (.github/CODEOWNERS is the only place that says who owns which path, ADR 0211).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SERVICE_DIRS = ['scraper', 'analytics', 'web', 'api', 'contracts'];
const SKIP_DIRS = new Set(['.git', 'node_modules', '.agents', '.venv', '__pycache__']);
const SKIP_PREFIXES = ['.claude/skills/openspec-', 'openspec/changes/archive'];
// Per-change OpenSpec files and generic names that are referred to without a fixed location.
// security-audit.md is a planned deliverable (integration-plan.md section 7); remove it from this set
// once the file exists so a later rename is caught.
const IGNORED_NAMES = new Set(['follow-ups.md', 'tasks.md', 'proposal.md', 'design.md', 'spec.md', 'SKILL.md', 'security-audit.md']);

// Ownership rule. People are named by first name in prose; their handles live in CODEOWNERS only.
const PEOPLE = ['Adam', 'Kacper', 'Damian'];
// Directories plus the names of the status domains (`dashboard` is web/, `platform` is analytics/, api/, contracts/).
const MODULE_WORDS = ['scraper', 'analytics', 'api', 'web', 'contracts', 'infra', 'dashboard', 'platform'];
// History keeps the names it had (ADRs, the AI log); in-flight changes are archived (and skipped) later.
const OWNERSHIP_SKIP = ['.docs/decisions/', '.docs/ai-workflow.md', 'openspec/changes/'];
// Spec scenario steps are hypothetical examples ("GIVEN analytics/ is owned by Damian").
const SCENARIO_STEP = /^\s*-\s*\*\*(?:GIVEN|WHEN|THEN|AND)\*\*/;
const NAME = `(?:${PEOPLE.join('|')})\\b`;
const MODULE = `(?<![\\w/-])\`?(?:${MODULE_WORDS.join('|')})/?\`?`;
const OWNERSHIP_PATTERNS = [
  new RegExp(`\\b(?:owners?|owned by)\\b[\\s:*(]*${NAME}`, 'i'), // owner Damian, **Owner:** Damian, owned by Kacper
  new RegExp(`\\b${NAME}'s module`), // Adam's module
  new RegExp(`${MODULE}\\s*\\(${NAME}`), // scraper (Adam), web/ dashboard (Kacper)
  new RegExp(`\`(?:${MODULE_WORDS.join('|')})/\` ${NAME}`), // `scraper/` Adam
  /^\s*\|.*\|\s*Owners?\s*\|/i, // an Owner table column
];

function walk(root, rel = '') {
  const out = [];
  for (const entry of fs.readdirSync(path.join(root, rel), { withFileTypes: true })) {
    const childRel = path.posix.join(rel, entry.name);
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name) || SKIP_PREFIXES.some((p) => childRel.startsWith(p))) continue;
      out.push(...walk(root, childRel));
    } else if (entry.name.endsWith('.md')) {
      out.push(childRel);
    }
  }
  return out;
}

const isExternalOrPlaceholder = (t) => /^(?:[a-z]+:|#|mailto:)/i.test(t) || /[*<>{}$]/.test(t) || /NNNN|YYYY/.test(t);

function resolves(root, fileRel, target) {
  const clean = target.split('#')[0];
  if (!clean) return true;
  const fromFile = path.resolve(root, path.dirname(fileRel), clean);
  const fromRoot = path.resolve(root, clean);
  return fs.existsSync(fromFile) || fs.existsSync(fromRoot);
}

function referencesIn(text) {
  const refs = [];
  text.split('\n').forEach((line, i) => {
    for (const m of line.matchAll(/\[[^\]]*\]\(([^)\s]+)\)/g)) refs.push({ line: i + 1, target: m[1] });
    for (const m of line.matchAll(/`([^`\s]+\.md(?:#[\w-]+)?)`/g)) refs.push({ line: i + 1, target: m[1] });
  });
  return refs;
}

export function checkDocs(root) {
  const problems = [];
  const files = walk(root);

  for (const file of files) {
    const text = fs.readFileSync(path.join(root, file), 'utf8');
    for (const { line, target } of referencesIn(text)) {
      if (isExternalOrPlaceholder(target) || IGNORED_NAMES.has(path.posix.basename(target.split('#')[0]))) continue;
      if (!resolves(root, file, target)) problems.push({ file, line, problem: `broken reference: ${target}` });
    }
  }

  const decisionsDir = path.join(root, '.docs', 'decisions');
  if (fs.existsSync(decisionsDir)) {
    const indexPath = path.join(decisionsDir, 'README.md');
    const index = fs.existsSync(indexPath) ? fs.readFileSync(indexPath, 'utf8') : '';
    for (const name of fs.readdirSync(decisionsDir)) {
      if (!/^\d{4}-.+\.md$/.test(name) || name.startsWith('0000-')) continue;
      if (!index.includes(name)) problems.push({ file: `.docs/decisions/${name}`, line: 1, problem: `${name} is not listed in .docs/decisions/README.md` });
    }
  }

  const services = SERVICE_DIRS.filter((dir) => fs.existsSync(path.join(root, dir)) && fs.statSync(path.join(root, dir)).isDirectory());
  for (const dir of services) {
    if (!fs.existsSync(path.join(root, dir, 'CLAUDE.md'))) problems.push({ file: dir, line: 1, problem: `${dir}/ has no CLAUDE.md` });
  }

  problems.push(...checkCodeowners(root, services));

  const extra = ['openspec/config.yaml', ...composeFiles(root)];
  for (const file of [...files, ...extra.filter((f) => fs.existsSync(path.join(root, f)))]) {
    if (OWNERSHIP_SKIP.some((p) => file.startsWith(p))) continue;
    fs.readFileSync(path.join(root, file), 'utf8').split('\n').forEach((text, i) => {
      if (SCENARIO_STEP.test(text) || !OWNERSHIP_PATTERNS.some((re) => re.test(text))) return;
      problems.push({ file, line: i + 1, problem: 'per-person ownership statement: link .github/CODEOWNERS instead' });
    });
  }
  return problems;
}

// compose*.yaml at the root and directly in each module directory (compose.yaml, compose.renderer.yaml, ...)
function composeFiles(root) {
  return ['', ...SERVICE_DIRS, 'infra'].flatMap((dir) => {
    const full = path.join(root, dir);
    if (!fs.existsSync(full) || !fs.statSync(full).isDirectory()) return [];
    return fs.readdirSync(full).filter((n) => /^compose[\w.-]*\.ya?ml$/.test(n)).map((n) => path.posix.join(dir, n));
  });
}

// Every existing service directory has a `/<dir>/` line with at least one @handle. infra/ and the other
// shared areas have no owner on purpose, so they are not required.
function checkCodeowners(root, services) {
  if (!services.length) return [];
  const file = '.github/CODEOWNERS';
  const full = path.join(root, file);
  if (!fs.existsSync(full)) return [{ file, line: 1, problem: `${file} is missing; it maps ${services.join(', ')} to owners` }];
  const owned = new Set();
  for (const raw of fs.readFileSync(full, 'utf8').split('\n')) {
    const [pattern, ...owners] = raw.replace(/#.*/, '').trim().split(/\s+/);
    if (pattern && owners.some((o) => /^@[A-Za-z0-9-]+(?:\/[A-Za-z0-9._-]+)?$/.test(o))) owned.add(pattern);
  }
  return services.filter((dir) => !owned.has(`/${dir}/`)).map((dir) => ({ file, line: 1, problem: `no /${dir}/ line with an @owner in ${file}` }));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const root = path.resolve(process.argv[2] || process.cwd());
  const problems = checkDocs(root);
  for (const p of problems) process.stderr.write(`${p.file}:${p.line}: ${p.problem}\n`);
  process.stdout.write(problems.length ? `docs-check: ${problems.length} problem(s)\n` : 'docs-check: ok\n');
  process.exit(problems.length ? 1 : 0);
}
