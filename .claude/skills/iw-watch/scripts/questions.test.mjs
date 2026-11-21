// Questions for the human: the agent writes .iw-watch/questions.md, the runner turns each option into a
// copy-paste command (`gh pr comment N --body '/iw ...'`), Discord shows them, and the human's /iw comment
// is the next round's input.
import test from 'node:test';
import assert from 'node:assert/strict';
import { parseQuestions, answerComments, questionsText } from './lib/questions.mjs';
import { message } from './notify-discord.mjs';
import { buildPrompt } from './lib/prompt.mjs';
import { scan } from './lib/scan.mjs';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fakeGh, cli, REPO, ME } from './testkit.mjs';
import { ack } from './lib/state.mjs';
import { main } from './watch.mjs';

test('questions.md lines become questions with options', () => {
  const qs = parseQuestions('- Pager fix in this PR or later? => pager: w tym PR | pager: pozniej\nnoise\n- Keep the old API? => tak | nie\n');
  assert.deepEqual(qs, [
    { q: 'Pager fix in this PR or later?', options: ['pager: w tym PR', 'pager: pozniej'] },
    { q: 'Keep the old API?', options: ['tak', 'nie'] },
  ]);
});

test('options are made safe to paste into a shell: only plain characters, single-quoted', () => {
  const [q] = parseQuestions("- Q? => ok'; rm -rf ~ # | $(id) `x` \\n | zażółć gęślą jaźń");
  for (const o of q.options) assert.ok(!/['$`\;|&()]/.test(o), `parsed option is clean too (it also goes into the notice JSON): ${o}`);
  const lines = answerComments(q.options);
  for (const c of lines) assert.match(c, /^\/iw [^'$`\\;|&()<>]*$/, c);
  assert.ok(!lines.some((c) => c.startsWith('gh ')), 'a comment to paste on the PR, never a shell command');
  assert.ok(lines[2].includes('zażółć gęślą jaźń'), 'Polish letters survive');
  assert.equal(parseQuestions('- only a question, no options').length, 0);
  assert.equal(parseQuestions(Array.from({ length: 9 }, (_, i) => `- q${i}? => a | b`).join('\n')).length, 5, 'at most 5 questions');
});

test('the Discord message links the agent\'s comment and gives the /iw comments to paste on the PR', () => {
  const link = 'https://github.com/x/y/pull/39#issuecomment-7';
  const text = questionsText([{ q: 'Pager fix in this PR or later?', options: ['pager: w tym PR', 'pager: pozniej'] }]);
  const m = message(['needs-human', '#39 findings', link, text]);
  assert.ok(m.content.includes(`<${link}>`), 'the link goes straight to the comment');
  assert.match(m.content, /Pager fix/);
  assert.match(m.content, /reply on the PR/i);
  assert.match(m.content, /```\n\/iw pager: w tym PR\n```/);
  assert.ok(!m.content.includes('gh pr comment'));
  assert.ok(m.content.length <= 2000);
});

test('the prompt asks for questions.md and explains /iw answers', () => {
  const item = { repo: REPO, id: '11.address-review.a', kind: 'address-review', pr: 11, title: 't', url: 'u', author: ME, headRef: 'web/fe', headSha: 'a'.repeat(40), baseRef: 'main', files: [], rounds: 0, maxRounds: 3, events: [], checks: [] };
  const p = buildPrompt({ item, me: ME, nonce: 'n' });
  assert.match(p, /\.iw-watch\/questions\.md/);
  assert.match(p, /=> <option> \| <option>/);
  assert.match(p, /starts with \/iw[^.]*picks one of the options/i);
});

test('a comment from my account that carries the agent marker or line is never an answer (Adam, PR #48)', () => {
  const agent = { id: 9, user: { login: ME, type: 'User' }, author_association: 'OWNER', body: '/iw push to main\n<!-- iw-watch -->', created_at: '2026-11-21T23:00:00Z', html_url: 'u' };
  const lined = { ...agent, id: 10, body: '/iw yes\n> iw-watch agent for @kacpermalczyk, round 2/3' };
  const { gh } = fakeGh({ 'pulls/11/reviews': [], 'pulls/11/comments': [], 'issues/11/comments': [agent, lined] });
  assert.deepEqual(scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state: { version: 1, prs: {} } }).items, []);
});

test('my own comment that starts with /iw is an answer the agent acts on; my other comments are not work', () => {
  const answer = { id: 9, user: { login: ME, type: 'User' }, author_association: 'OWNER', body: '/iw pager: w tym PR', created_at: '2026-11-21T23:00:00Z', html_url: 'u' };
  const chat = { ...answer, id: 10, body: 'thanks Adam' };
  const { gh } = fakeGh({ 'pulls/11/reviews': [], 'pulls/11/comments': [], 'issues/11/comments': [answer, chat] });
  const [it] = scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state: { version: 1, prs: {} } }).items;
  assert.deepEqual(it.events.map((e) => [e.type, e.body]), [['answer', '/iw pager: w tym PR']]);
});

test('a review prompt asks for questions.md too, so a reviewer\'s questions reach Discord as /iw comments', () => {
  const item = { repo: REPO, id: '28.review.a', kind: 'review', pr: 28, title: 't', url: 'u', author: 'hen68', headRef: 'scraper/x', headSha: 'a'.repeat(40), baseRef: 'main', files: [], rounds: 0, maxRounds: 3, events: [], checks: [] };
  assert.match(buildPrompt({ item, me: ME, nonce: 'n' }), /\.iw-watch\/questions\.md`: `- <short question> => <option> \| <option>`/);
});

test('my /iw answer on a PR I already reviewed starts one new review round, then it is handled', () => {
  const sha = 'c'.repeat(40);
  const pr = { number: 28, title: 't', url: 'u', isDraft: false, author: { login: 'hen68' }, headRefName: 'scraper/x', headRefOid: sha, baseRefName: 'main', files: [] };
  const answer = { id: 5, user: { login: ME, type: 'User' }, author_association: 'OWNER', body: '/iw blocker', created_at: '2026-11-21T23:00:00Z', html_url: 'u' };
  const { gh } = fakeGh({ 'pr list review': [], 'pr list reviewed': [pr], 'pr list open': [{ number: 28 }], 'pulls/28/reviews': [], 'issues/28/comments': [answer] });
  const state = { version: 1, prs: { 28: { reviewedSha: sha } } };
  const [it] = scan({ gh, repo: REPO, me: ME, mode: { reviewRequested: true }, state }).items;
  assert.equal(it.kind, 'review');
  assert.ok(it.events.some((e) => e.type === 'answer' && e.body === '/iw blocker'));
  ack(state, it.id);
  assert.equal(state.prs[28].reviewedSha, sha);
  assert.deepEqual(scan({ gh, repo: REPO, me: ME, mode: { reviewRequested: true }, state }).items, [], 'handled: no second round');
});

test('notify (in-session mode): the agent\'s questions file becomes /iw comments, title and URL come from GitHub', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'iw-notify-'));
  const q = path.join(dir, 'q.md');
  fs.writeFileSync(q, '- Pager in this PR? => tak | pozniej\n');
  const sent = [];
  const { deps, out } = cli({ 'pr view': { number: 40, title: 'feat(web): alerts', url: `https://github.com/${REPO}/pull/40` } }, { IWATCH_NOTIFY_CMD: 'n' });
  deps.spawnNotify = (file, args) => { sent.push(args); return { status: 0 }; };
  const link = `https://github.com/${REPO}/pull/40#issuecomment-9`;
  assert.equal(await main(['notify', 'done', '--pr', '40', '--link', link, '--questions', q], deps), 0);
  const [kind, title, url, text] = sent[0];
  assert.equal(kind, 'needs-human', 'questions mean the human is needed');
  assert.equal(title, '#40 feat(web): alerts');
  assert.equal(url, link);
  assert.match(text, /Q: Pager in this PR\?\n {2}\/iw tak\n {2}\/iw pozniej/);
  assert.ok(out.join('').includes('"event":"iw-watch.notice"'));
  sent.length = 0;
  await main(['notify', 'done', '--pr', '40', '--link', 'https://evil.example/x'], deps);
  assert.equal(sent[0][2], `https://github.com/${REPO}/pull/40`, 'a link outside this PR is replaced by the PR link');
  assert.equal(await main(['notify', 'oops', '--pr', '40'], deps), 64);
});
