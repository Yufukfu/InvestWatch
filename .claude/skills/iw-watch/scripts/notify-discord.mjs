#!/usr/bin/env node
// A notifier for IWATCH_NOTIFY_CMD: posts each iw-watch notice to a Discord channel through a webhook.
//   export IWATCH_DISCORD_WEBHOOK=https://discord.com/api/webhooks/<id>/<token>   (a secret: .env, never committed)
//   export IWATCH_NOTIFY_CMD="node /abs/path/.claude/skills/iw-watch/scripts/notify-discord.mjs"
// The watcher calls it as: notify-discord.mjs <kind> <"#pr title"> <url>. No mentions are ever parsed, so a
// PR title cannot ping @everyone.
import { pathToFileURL } from 'node:url';

const LABEL = { done: '✅ done', 'draft-ready': '📝 draft ready', 'needs-human': '🙋 needs you' };
const WEBHOOK = /^https:\/\/(?:discord\.com|discordapp\.com)\/api\/webhooks\/\d+\/[A-Za-z0-9_-]+$/;

export function message([kind, title, url, text]) {
  // <url> keeps Discord from embedding a preview; the link points at the agent's comment when there is one
  const head = `**iw-watch** ${LABEL[kind] || kind}: ${title} <${url}>`.slice(0, 600);
  const fence = (s) => s.replace(/\`/g, "'");
  const lines = String(text || "").slice(0, 1300).split("\n");
  const answers = lines.filter((l) => /^\s*\/iw /.test(l));
  const notes = lines.filter((l) => !/^\s*\/iw /.test(l) && l.trim());
  let body = notes.length ? `\n${fence(notes.join("\n"))}` : "";
  // one copy box per answer: paste it as a comment on the PR
  if (answers.length) body += `\nReply on the PR with one of these comments:\n${answers.map((a) => `\`\`\`\n${fence(a.trim())}\n\`\`\``).join("\n")}`;
  return { content: `${head}${body}`, allowed_mentions: { parse: [] } };
}

export async function send(argv, { env = process.env, fetch = globalThis.fetch, stderr = (s) => process.stderr.write(s) } = {}) {
  const hook = String(env.IWATCH_DISCORD_WEBHOOK || '');
  if (!WEBHOOK.test(hook)) {
    stderr('notify-discord: IWATCH_DISCORD_WEBHOOK is not set to a https://discord.com/api/webhooks/... URL\n');
    return 2;
  }
  const res = await fetch(hook, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(message(argv)), signal: AbortSignal.timeout(10000) });
  if (!res.ok) {
    stderr(`notify-discord: the webhook answered HTTP ${res.status}\n`);
    return 1;
  }
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  send(process.argv.slice(2)).then((code) => { process.exitCode = code; }, (e) => { process.stderr.write(`notify-discord: ${e.name}\n`); process.exitCode = 1; });
}
