// CODEOWNERS parser: the subset GitHub documents and this repository uses (directory and glob patterns,
// last match wins). Anything else (negation, character classes, escapes, a line with no owner) throws,
// because a guessed owner routes an issue or a review to the wrong person.

const OWNER = /^@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\/[A-Za-z0-9._-]+)?$|^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const UNSUPPORTED = /[!\[\]\\]/;

function toRegex(pattern) {
  const dirOnly = pattern.endsWith('/');
  let body = pattern.replace(/^\//, '').replace(/\/$/, '');
  // a separator at the start or in the middle anchors the pattern to the repository root
  const anchored = pattern.startsWith('/') || body.includes('/');
  let re = '';
  for (let i = 0; i < body.length; i += 1) {
    const c = body[i];
    if (c === '*' && body[i + 1] === '*') {
      if (body[i + 2] === '/') { re += '(?:.*/)?'; i += 2; } else { re += '.*'; i += 1; }
    } else if (c === '*') re += '[^/]*';
    else if (c === '?') re += '[^/]';
    else re += c.replace(/[.+^${}()|]/g, '\\$&');
  }
  if (body === '*' ) return /^.*$/;
  const prefix = anchored ? '^' : '^(?:.*/)?';
  const suffix = dirOnly ? '/.*$' : '(?:/.*)?$';
  return new RegExp(prefix + re + suffix);
}

export function parseCodeowners(text) {
  const rules = [];
  text.split(/\r?\n/).forEach((raw, idx) => {
    const line = raw.trim();
    if (!line || line.startsWith('#')) return;
    const [pattern, ...rest] = line.split(/\s+/);
    const owners = rest.filter((o) => !o.startsWith('#'));
    const where = `CODEOWNERS line ${idx + 1}`;
    if (UNSUPPORTED.test(pattern)) throw new Error(`${where}: unsupported pattern syntax in ${JSON.stringify(pattern)}`);
    if (owners.length === 0) throw new Error(`${where}: pattern ${JSON.stringify(pattern)} has no owner`);
    for (const o of owners) {
      if (!OWNER.test(o)) throw new Error(`${where}: owner ${JSON.stringify(o)} is not @login, @org/team or an email`);
    }
    rules.push({ pattern, owners: owners.map((o) => o.replace(/^@/, '')), re: toRegex(pattern) });
  });
  return rules;
}

/** Owners of `file` (repository-relative, no leading slash): the last matching rule, or [] */
export function ownerOf(rules, file) {
  const p = file.replace(/^\.?\//, '');
  let owners = [];
  for (const r of rules) if (r.re.test(p)) owners = r.owners;
  return owners;
}

/** Patterns (as written, without a leading slash) whose owners include `login` */
export function ownedDirs(rules, login) {
  const me = login.toLowerCase();
  return rules.filter((r) => r.owners.some((o) => o.toLowerCase() === me)).map((r) => r.pattern.replace(/^\//, ''));
}

/** Parse the CODEOWNERS of `ref` (the default branch), so a PR cannot reroute its own review. null if absent. */
export function loadCodeowners({ git, ref }) {
  let text;
  try {
    text = git(['show', `${ref}:.github/CODEOWNERS`]);
  } catch {
    return null;
  }
  return parseCodeowners(text);
}
