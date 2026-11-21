// Notices for the human: one JSON log line on stdout each, plus an optional command
// (IWATCH_NOTIFY_CMD, for example a script that posts to a Discord webhook or calls terminal-notifier).
// The command gets kind, title and URL as separate argv values, never through a shell, and a failing
// notifier never fails the run.
import { spawnSync } from 'node:child_process';

export const KINDS = ['done', 'draft-ready', 'needs-human'];

export function makeNotifier({ env, stdout, stderr, now = () => Date.now(), spawn = spawnSync }) {
  const cmd = String(env.IWATCH_NOTIFY_CMD || '').trim().split(/\s+/).filter(Boolean);
  return (notice) => {
    if (!KINDS.includes(notice.kind)) throw new Error(`unknown notice kind ${notice.kind}`);
    const line = { ts: new Date(now()).toISOString(), level: notice.kind === 'needs-human' ? 'warn' : 'info', event: 'iw-watch.notice', ...notice };
    stdout(`${JSON.stringify(line)}\n`);
    if (!cmd.length) return;
    try {
      const r = spawn(cmd[0], [...cmd.slice(1), notice.kind, `#${notice.pr} ${notice.title}`, notice.url || ''], { shell: false, stdio: 'ignore', timeout: 15000 });
      if (r?.error) throw r.error;
    } catch (e) {
      stderr(`iw-watch: notify command failed (${e.message}); the run goes on\n`);
    }
  };
}
