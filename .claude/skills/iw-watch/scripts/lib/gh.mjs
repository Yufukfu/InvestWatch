// Thin `gh` wrapper: argv only (never a shell), JSON out, errors sorted into what the human must do.
import { execFileSync } from 'node:child_process';

export class GhError extends Error {
  constructor(kind, message) {
    super(message);
    this.kind = kind; // missing | auth | rate | other
  }
}

function classify(e, args) {
  if (e instanceof GhError) return e;
  if (e.code === 'ENOENT') return new GhError('missing', 'gh is not installed or not on PATH: install it from https://cli.github.com and run `gh auth login`');
  const stderr = String(e.stderr || e.message || '');
  if (/gh auth login|not logged in|authentication required|HTTP 401|Bad credentials/i.test(stderr)) {
    return new GhError('auth', 'gh is not logged in: run `gh auth login`');
  }
  if (/rate limit|HTTP 429|secondary rate/i.test(stderr)) {
    return new GhError('rate', 'GitHub rate limit reached; nothing was changed, the next scheduled run retries');
  }
  return new GhError('other', `gh ${args.slice(0, 3).join(' ')} failed: ${stderr.trim().split('\n')[0]}`);
}

/**
 * `gh api --paginate` on gh 2.39 (no --slurp) prints one JSON array per page back to back: `[...][...]`.
 * Split the top-level values with a scanner that respects strings, then concatenate the arrays.
 */
export function parseJsonStream(text) {
  const values = [];
  let depth = 0; let start = -1; let inStr = false; let esc = false;
  for (let i = 0; i < text.length; i += 1) {
    const c = text[i];
    if (inStr) {
      if (esc) esc = false;
      else if (c === '\\') esc = true;
      else if (c === '"') inStr = false;
      continue;
    }
    if (c === '"') { inStr = true; if (depth === 0) throw new SyntaxError('bare string at top level'); continue; }
    if (c === '[' || c === '{') { if (depth === 0) start = i; depth += 1; }
    else if (c === ']' || c === '}') {
      depth -= 1;
      if (depth < 0) throw new SyntaxError('unbalanced JSON');
      if (depth === 0) values.push(JSON.parse(text.slice(start, i + 1)));
    } else if (depth === 0 && !/\s/.test(c)) throw new SyntaxError(`unexpected ${JSON.stringify(c)} at top level`);
  }
  if (depth !== 0 || inStr) throw new SyntaxError('truncated JSON');
  if (values.length === 1) return values[0];
  if (values.every(Array.isArray)) return values.flat();
  throw new SyntaxError('several top-level JSON values that are not all arrays');
}

export function makeGh({ exec = execFileSync, cwd } = {}) {
  return (args) => {
    let out;
    try {
      out = exec('gh', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: 64 * 1024 * 1024 });
    } catch (e) {
      throw classify(e, args);
    }
    const text = String(out).trim();
    if (!text) return null;
    try {
      return parseJsonStream(text);
    } catch (e) {
      throw new GhError('other', `gh ${args.slice(0, 3).join(' ')} printed something that is not JSON (${e.message})`);
    }
  };
}
