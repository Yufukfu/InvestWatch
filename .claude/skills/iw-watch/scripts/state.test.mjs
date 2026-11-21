import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { stateDir, loadState, saveState, ack, itemId, recordSession, dropClosed, acquireLock, releaseLock, STALE_LOCK_MS } from './lib/state.mjs';
import { MARKER, countRounds, capReached } from './lib/rounds.mjs';

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'iw-watch-'));

test('the state directory is outside the repository, per repository', () => {
  assert.equal(stateDir({ env: { XDG_STATE_HOME: '/s' }, home: '/h', repo: 'Yufukfu/InvestWatch' }), '/s/iw-watch/Yufukfu__InvestWatch');
  assert.equal(stateDir({ env: {}, home: '/h', repo: 'a/b' }), '/h/.local/state/iw-watch/a__b');
  assert.throws(() => stateDir({ env: {}, home: '/h', repo: '../x' }), /repository/);
});

test('missing state starts empty; save then load round-trips', () => {
  const dir = tmp();
  assert.deepEqual(loadState(dir), { version: 1, prs: {} });
  const s = { version: 1, prs: { 7: { seenAt: '2026-11-21T10:00:00Z' } } };
  saveState(dir, s);
  assert.deepEqual(loadState(dir), s);
  assert.deepEqual(fs.readdirSync(dir), ['state.json'], 'no temp file is left behind');
});

test('a write that dies before the rename leaves the previous file intact', () => {
  const dir = tmp();
  saveState(dir, { version: 1, prs: { 1: { seenAt: 'old' } } });
  const broken = { ...fs, renameSync: () => { throw new Error('killed'); } };
  assert.throws(() => saveState(dir, { version: 1, prs: { 1: { seenAt: 'new' } } }, { fs: broken }), /killed/);
  assert.equal(loadState(dir).prs[1].seenAt, 'old');
});

test('a corrupt state file is moved aside, reported, and the run starts empty', () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, 'state.json'), '{not json');
  const logs = [];
  const s = loadState(dir, { log: (m) => logs.push(m), now: () => new Date('2026-11-21T12:00:00Z') });
  assert.deepEqual(s, { version: 1, prs: {} });
  const backups = fs.readdirSync(dir).filter((f) => f.startsWith('state.json.corrupt-'));
  assert.equal(backups.length, 1);
  assert.equal(fs.readFileSync(path.join(dir, backups[0]), 'utf8'), '{not json', 'the backup keeps the bytes');
  assert.match(logs[0], /corrupt/);
  assert.ok(!fs.existsSync(path.join(dir, 'state.json')));
});

test('ack moves the cursor of the item kind and nothing else', () => {
  const s = { version: 1, prs: {} };
  ack(s, itemId({ kind: 'address-review', pr: 12, cursor: '2026-11-21T10:05:00Z' }));
  assert.equal(s.prs[12].seenAt, '2026-11-21T10:05:00Z');
  assert.equal(s.prs[12].reviewedSha, undefined);
  ack(s, itemId({ kind: 'review', pr: 12, cursor: 'abc123' }));
  assert.equal(s.prs[12].reviewedSha, 'abc123');
  // an older cursor never moves the seen time backwards
  ack(s, itemId({ kind: 'address-review', pr: 12, cursor: '2026-11-21T09:00:00Z' }));
  assert.equal(s.prs[12].seenAt, '2026-11-21T10:05:00Z');
  ack(s, itemId({ kind: 'cap-reached', pr: 12, cursor: 'abc123' }));
  assert.equal(s.prs[12].capNotifiedSha, 'abc123');
  assert.throws(() => ack(s, 'garbage'), /item id/);
  assert.throws(() => ack(s, '12.unknown.x'), /item id/);
});

test('sessions are counted per PR, and closed PRs are dropped', () => {
  const s = { version: 1, prs: {} };
  recordSession(s, 5); recordSession(s, 5); recordSession(s, 6);
  assert.equal(s.prs[5].sessions, 2);
  dropClosed(s, new Set([6]));
  assert.deepEqual(Object.keys(s.prs), ['6']);
});

test('the lock is exclusive, released, and replaced when stale', () => {
  const dir = tmp();
  const t0 = Date.parse('2026-11-21T12:00:00Z');
  const first = acquireLock(dir, { now: () => t0 });
  assert.ok(first, 'first runner gets the lock');
  assert.equal(acquireLock(dir, { now: () => t0 + 60_000 }), null, 'second runner is refused');
  assert.equal(acquireLock(dir, { now: () => t0 + STALE_LOCK_MS - 1 }), null, 'just under the threshold is not stale');
  const stolen = acquireLock(dir, { now: () => t0 + STALE_LOCK_MS + 1 });
  assert.ok(stolen, 'a lock older than 30 minutes is replaced');
  releaseLock(stolen);
  assert.ok(acquireLock(dir, { now: () => t0 }), 'released lock can be taken again');
  assert.equal(STALE_LOCK_MS, 30 * 60 * 1000);
});

const fixture = JSON.parse(fs.readFileSync(new URL('./fixtures/pr-comments.json', import.meta.url), 'utf8'));

test('rounds are the larger of marked comments by me and recorded sessions', () => {
  // the fixture has 2 marked comments by kacpermalczyk, 1 marked by someone else, 1 unmarked by me
  assert.equal(countRounds({ comments: fixture, me: 'kacpermalczyk', sessions: 0 }), 2);
  assert.equal(countRounds({ comments: fixture, me: 'kacpermalczyk', sessions: 3 }), 3);
  assert.equal(countRounds({ comments: fixture, me: 'hen68', sessions: 0 }), 1);
  assert.equal(countRounds({ comments: [], me: 'x', sessions: 0 }), 0);
  assert.equal(MARKER, '<!-- iw-watch -->');
});

test('the cap is reached at the limit, not after it', () => {
  assert.equal(capReached(2, 3), false);
  assert.equal(capReached(3, 3), true);
  assert.equal(capReached(4, 3), true);
});
