// Questions for the human: the agent writes .iw-watch/questions.md, the runner turns each option into a
// copy-paste command (`gh pr comment N --body '/iw ...'`), Discord shows them, and the human's /iw comment
// is the next round's input.
import test from 'node:test';
import assert from 'node:assert/strict';
import { parseQuestions, answerCommands } from './lib/questions.mjs';
import { message } from './notify-discord.mjs';
import { buildPrompt } from './lib/prompt.mjs';
import { scan } from './lib/scan.mjs';
import { fakeGh, REPO, ME } from './testkit.mjs';

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
  const cmds = answerCommands(11, q.options);
  for (const c of cmds) {
    assert.match(c, /^gh pr comment 11 --body '\/iw [^'$`\\;|&()<>]*'$/, c);
  }
  assert.ok(cmds[2].includes('zażółć gęślą jaźń'), 'Polish letters survive');
  assert.equal(parseQuestions('- only a question, no options').length, 0);
  assert.equal(parseQuestions(Array.from({ length: 9 }, (_, i) => `- q${i}? => a | b`).join('\n')).length, 5, 'at most 5 questions');
});

test('the Discord message carries the questions and the commands to copy', () => {
  const text = 'Q: Pager fix in this PR or later?\n  gh pr comment 39 --body \'/iw pager: w tym PR\'';
  const m = message(['needs-human', '#39 findings', 'https://github.com/x/y/pull/39', text]);
  assert.match(m.content, /Pager fix/);
  assert.match(m.content, /```[\s\S]*gh pr comment 39 --body '\/iw pager: w tym PR'[\s\S]*```/);
  assert.ok(m.content.length <= 2000);
});

test('the prompt asks for questions.md and explains /iw answers', () => {
  const item = { repo: REPO, id: '11.address-review.a', kind: 'address-review', pr: 11, title: 't', url: 'u', author: ME, headRef: 'web/fe', headSha: 'a'.repeat(40), baseRef: 'main', files: [], rounds: 0, maxRounds: 3, events: [], checks: [] };
  const p = buildPrompt({ item, me: ME, nonce: 'n' });
  assert.match(p, /\.iw-watch\/questions\.md/);
  assert.match(p, /=> <option> \| <option>/);
  assert.match(p, /starts with \/iw[^.]*answer/i);
});

test('my own comment that starts with /iw is an answer the agent acts on; my other comments are not work', () => {
  const answer = { id: 9, user: { login: ME, type: 'User' }, author_association: 'OWNER', body: '/iw pager: w tym PR', created_at: '2026-11-21T23:00:00Z', html_url: 'u' };
  const chat = { ...answer, id: 10, body: 'thanks Adam' };
  const { gh } = fakeGh({ 'pulls/11/reviews': [], 'pulls/11/comments': [], 'issues/11/comments': [answer, chat] });
  const [it] = scan({ gh, repo: REPO, me: ME, mode: { mine: true }, state: { version: 1, prs: {} } }).items;
  assert.deepEqual(it.events.map((e) => [e.type, e.body]), [['answer', '/iw pager: w tym PR']]);
});
