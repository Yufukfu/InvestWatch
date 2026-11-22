#!/usr/bin/env node
// AI log: one file per entry in .docs/ai-log/, so parallel PRs never edit the same file.
// Usage:
//   node ai-log.mjs check  [repoRoot]   exit 1 if an entry is malformed (run in CI)
//   node ai-log.mjs render [repoRoot]   print the whole log as one Markdown table, oldest first
//   node ai-log.mjs new <who> <slug> [when]   print the path for a new entry and create it from the template
// No LLM, no network.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const LOG_DIR = path.join('.docs', 'ai-log');
export const PEOPLE = ['Adam', 'Kacper', 'Damian'];
// 2026-11-21T2300-adam-scraper-stack.md  (the time is the sort key; `when:` keeps the human-readable value)
export const NAME_RE = /^(\d{4}-\d{2}-\d{2})T(\d{4})-(adam|kacper|damian)-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$/;
const SECTIONS = ['What was done with AI', 'Outcome / lesson'];

export function parseEntry(text) {
  const m = text.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!m) return null;
  const meta = Object.fromEntries(
    m[1].split('\n').filter(Boolean).map((l) => {
      const i = l.indexOf(':');
      return [l.slice(0, i).trim(), l.slice(i + 1).trim()];
    }),
  );
  const sections = {};
  for (const part of m[2].split(/^## /m).slice(1)) {
    const nl = part.indexOf('\n');
    sections[part.slice(0, nl).trim()] = part.slice(nl + 1).trim();
  }
  return { meta, sections };
}

export function listEntries(root) {
  const dir = path.join(root, LOG_DIR);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((n) => n.endsWith('.md') && n !== 'README.md').sort();
}

export function checkLog(root) {
  const problems = [];
  // A stale branch merged with "keep both" would bring the old table back; entries belong in .docs/ai-log/.
  const workflow = path.join(root, '.docs', 'ai-workflow.md');
  if (fs.existsSync(workflow) && /^\| When \| Who \|/m.test(fs.readFileSync(workflow, 'utf8'))) {
    problems.push({ file: '.docs/ai-workflow.md', problem: 'has a log table again; move its rows to .docs/ai-log/ with `ai-log.mjs new`' });
  }
  for (const name of listEntries(root)) {
    const file = path.posix.join('.docs/ai-log', name);
    const nm = name.match(NAME_RE);
    if (!nm) {
      problems.push({ file, problem: 'file name must be YYYY-MM-DDTHHMM-<adam|kacper|damian>-<slug>.md' });
      continue;
    }
    const entry = parseEntry(fs.readFileSync(path.join(root, LOG_DIR, name), 'utf8'));
    if (!entry) {
      problems.push({ file, problem: 'missing front matter (--- when / who ---)' });
      continue;
    }
    if (!entry.meta.when) problems.push({ file, problem: 'front matter has no `when:`' });
    if (!PEOPLE.includes(entry.meta.who)) problems.push({ file, problem: `\`who:\` must be one of ${PEOPLE.join(', ')}` });
    else if (entry.meta.who.toLowerCase() !== nm[3]) problems.push({ file, problem: `\`who: ${entry.meta.who}\` does not match the file name` });
    for (const s of SECTIONS) {
      if (!entry.sections[s]) problems.push({ file, problem: `missing or empty section "## ${s}"` });
      else if (/^TODO\b/.test(entry.sections[s])) problems.push({ file, problem: `section "## ${s}" is still TODO` });
    }
  }
  return problems;
}

const cell = (s) => s.replace(/\s*\n\s*/g, ' ').replace(/\|/g, '\\|');

export function renderLog(root) {
  const rows = ['| When | Who | What was done with AI | Outcome / lesson |', '|---|---|---|---|'];
  for (const name of listEntries(root)) {
    const e = parseEntry(fs.readFileSync(path.join(root, LOG_DIR, name), 'utf8'));
    if (!e) continue;
    rows.push(`| ${cell(e.meta.when ?? '')} | ${cell(e.meta.who ?? '')} | ${cell(e.sections[SECTIONS[0]] ?? '')} | ${cell(e.sections[SECTIONS[1]] ?? '')} |`);
  }
  return rows.join('\n') + '\n';
}

export function newEntry(root, who, slug, when, now = new Date()) {
  const person = PEOPLE.find((p) => p.toLowerCase() === String(who).toLowerCase());
  if (!person) throw new Error(`who must be one of ${PEOPLE.join(', ')}`);
  const cleanSlug = String(slug).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const pad = (n) => String(n).padStart(2, '0');
  const stamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}${pad(now.getMinutes())}`;
  const name = `${stamp}-${person.toLowerCase()}-${cleanSlug}.md`;
  const label = when ?? `${now.toLocaleDateString('en-GB', { weekday: 'short' })} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
  const full = path.join(root, LOG_DIR, name);
  if (fs.existsSync(full)) throw new Error(`${full} already exists`);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, `---\nwhen: ${label}\nwho: ${person}\n---\n\n## ${SECTIONS[0]}\n\nTODO\n\n## ${SECTIONS[1]}\n\nTODO\n`);
  return path.posix.join('.docs/ai-log', name);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [cmd, ...args] = process.argv.slice(2);
  const defaultRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
  if (cmd === 'check') {
    const problems = checkLog(args[0] ?? defaultRoot);
    for (const p of problems) console.error(`${p.file}: ${p.problem}`);
    if (problems.length) process.exit(1);
    console.log('ai-log: ok');
  } else if (cmd === 'render') {
    process.stdout.write(renderLog(args[0] ?? defaultRoot));
  } else if (cmd === 'new' && args.length >= 2) {
    console.log(newEntry(defaultRoot, args[0], args[1], args[2]));
  } else {
    console.error('usage: ai-log.mjs check [root] | render [root] | new <who> <slug> [when]');
    process.exit(2);
  }
}
