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

export function makeGh({ exec = execFileSync, cwd } = {}) {
  return (args) => {
    let out;
    try {
      out = exec('gh', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: 64 * 1024 * 1024 });
    } catch (e) {
      throw classify(e, args);
    }
    const text = String(out).trim();
    return text ? JSON.parse(text) : null;
  };
}
