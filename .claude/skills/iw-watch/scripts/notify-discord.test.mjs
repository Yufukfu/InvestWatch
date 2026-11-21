import test from 'node:test';
import assert from 'node:assert/strict';
import { message, send } from './notify-discord.mjs';

test('the message names the kind, the PR and the link, and mentions nobody', () => {
  const m = message(['needs-human', '#11 docs(web): frontend @everyone', 'https://github.com/Yufukfu/InvestWatch/pull/11']);
  assert.match(m.content, /needs you/);
  assert.match(m.content, /#11/);
  assert.match(m.content, /https:\/\/github\.com\/Yufukfu\/InvestWatch\/pull\/11/);
  assert.deepEqual(m.allowed_mentions, { parse: [] }, 'a PR title cannot ping @everyone');
  assert.ok(m.content.length <= 2000);
});

test('send posts JSON to the webhook from the environment, and refuses anything but a Discord webhook URL', async () => {
  const calls = [];
  const fetch = async (url, init) => { calls.push({ url, init }); return { ok: true, status: 204 }; };
  const url = 'https://discord.com/api/webhooks/1/abc';
  assert.equal(await send(['done', '#11 t', 'https://github.com/x/y/pull/11'], { env: { IWATCH_DISCORD_WEBHOOK: url }, fetch }), 0);
  assert.equal(calls[0].url, url);
  assert.equal(calls[0].init.method, 'POST');
  assert.equal(JSON.parse(calls[0].init.body).allowed_mentions.parse.length, 0);
  for (const bad of ['', 'http://discord.com/api/webhooks/1/a', 'https://evil.example/api/webhooks/1/a', 'https://discord.com.evil.example/api/webhooks/1/a']) {
    calls.length = 0;
    assert.equal(await send(['done', 't', 'u'], { env: { IWATCH_DISCORD_WEBHOOK: bad }, fetch, stderr: () => {} }), 2, bad || 'empty');
    assert.equal(calls.length, 0, bad);
  }
});

test('a failing webhook exits non-zero without printing the URL (it is a secret)', async () => {
  const err = [];
  const url = 'https://discord.com/api/webhooks/1/SECRET-TOKEN';
  const code = await send(['done', 't', 'u'], { env: { IWATCH_DISCORD_WEBHOOK: url }, fetch: async () => ({ ok: false, status: 404 }), stderr: (s) => err.push(s) });
  assert.equal(code, 1);
  assert.match(err.join(''), /404/);
  assert.ok(!err.join('').includes('SECRET-TOKEN'));
});
