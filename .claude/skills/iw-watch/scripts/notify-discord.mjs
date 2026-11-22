#!/usr/bin/env node
// A notifier for IWATCH_NOTIFY_CMD: posts each iw-watch notice to a Discord channel through a webhook.
//   export IWATCH_DISCORD_WEBHOOK=https://discord.com/api/webhooks/<id>/<token>   (a secret: .env, never committed)
//   export IWATCH_NOTIFY_CMD="node /abs/path/.claude/skills/iw-watch/scripts/notify-discord.mjs"
//   export IWATCH_DISCORD_USER_ID=<your Discord user id>   (optional: pings you on needs-human and approved)
// The watcher calls it as: notify-discord.mjs <kind> <"#pr title"> <url>. Mentions are never parsed from the
// text, so a PR title cannot ping @everyone; the only ping allowed is the configured user id.
import { pathToFileURL } from 'node:url';

const LABEL = { done: '✅ done', 'draft-ready': '📝 draft ready', 'needs-human': '🙋 needs you', approved: '🎉 approved' };
const WEBHOOK = /^https:\/\/(?:discord\.com|discordapp\.com)\/api\/webhooks\/\d+\/[A-Za-z0-9_-]+$/;

const USER_ID = /^\d{15,22}$/;

export function message([kind, title, url, text], { userId } = {}) {
  const ping = (kind === 'needs-human' || kind === 'approved') && USER_ID.test(String(userId || '')) ? String(userId) : null;
  // <url> keeps Discord from embedding a preview; the link points at the agent's comment when there is one
  const fence = (s) => s.replace(/\`/g, "'");
  if (kind === 'approved') {
    // its own layout: good news first, then the PR, then who approved it
    const by = /^approved by (.+)$/i.exec(String(text || '').split('\n')[0].trim());
    const lines = [
      `🎉 Hey${ping ? ` <@${ping}>` : ''}, your PR is approved! You can merge it now.`,
      `**${fence(String(title)).slice(0, 300)}**`,
      `<${url}>`,
      ...(by ? [`✅ Approved by ${fence(by[1]).slice(0, 200)}`] : []),
    ];
    return { content: lines.join('\n'), allowed_mentions: { parse: [], ...(ping ? { users: [ping] } : {}) } };
  }
  const hey = ping ? `hey, I need you <@${ping}>\n` : '';
  const head = `${hey}**iw-watch** ${LABEL[kind] || kind}: ${title} <${url}>`.slice(0, 600);
  const lines = String(text || "").slice(0, 1300).split("\n");
  const answers = lines.filter((l) => /^\s*\/iw /.test(l));
  const notes = lines.filter((l) => !/^\s*\/iw /.test(l) && l.trim());
  let body = notes.length ? `\n${fence(notes.join("\n"))}` : "";
  // one copy box per answer: paste it as a comment on the PR
  if (answers.length) body += `\nReply on the PR with one of these comments:\n${answers.map((a) => `\`\`\`\n${fence(a.trim())}\n\`\`\``).join("\n")}`;
  return { content: `${head}${body}`, allowed_mentions: { parse: [], ...(ping ? { users: [ping] } : {}) } };
}

export async function send(argv, { env = process.env, fetch = globalThis.fetch, stderr = (s) => process.stderr.write(s) } = {}) {
  const hook = String(env.IWATCH_DISCORD_WEBHOOK || '');
  if (!WEBHOOK.test(hook)) {
    stderr('notify-discord: IWATCH_DISCORD_WEBHOOK is not set to a https://discord.com/api/webhooks/... URL\n');
    return 2;
  }
  const res = await fetch(hook, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(message(argv, { userId: env.IWATCH_DISCORD_USER_ID })), signal: AbortSignal.timeout(10000) });
  if (!res.ok) {
    stderr(`notify-discord: the webhook answered HTTP ${res.status}\n`);
    return 1;
  }
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  send(process.argv.slice(2)).then((code) => { process.exitCode = code; }, (e) => { process.stderr.write(`notify-discord: ${e.name}\n`); process.exitCode = 1; });
}
