import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { stateDir, loadState, saveState, ack, itemId, digest, setPending, isHandled, recordSession, dropClosed, acquireLock, releaseLock, refreshLock, STALE_LOCK_MS } from './lib/state.mjs';
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
  const s = { version: 1, prs: { 7: { sessions: 1 } } };
  saveState(dir, s);
  assert.deepEqual(loadState(dir), s);
  assert.deepEqual(fs.readdirSync(dir), ['state.json'], 'no temp file is left behind');
});

test('a write that dies before the rename leaves the previous file intact', () => {
  const dir = tmp();
  saveState(dir, { version: 1, prs: { 1: { sessions: 1 } } });
  const broken = { ...fs, renameSync: () => { throw new Error('killed'); } };
  assert.throws(() => saveState(dir, { version: 1, prs: { 1: { sessions: 2 } } }, { fs: broken }), /killed/);
  assert.equal(loadState(dir).prs[1].sessions, 1);
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

test('valid JSON of the wrong shape is treated as corrupt', () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, 'state.json'), '{"version":2,"prs":[]}');
  assert.deepEqual(loadState(dir, { log: () => {} }), { version: 1, prs: {} });
  assert.equal(fs.readdirSync(dir).filter((f) => f.includes('corrupt')).length, 1);
});

test('a ci-failed ack moves its own cursor, not the review cursor', () => {
  const s = { version: 1, prs: {} };
  ack(s, itemId({ kind: 'ci-failed', pr: 4, cursor: 'deadbeef' }));
  assert.equal(s.prs[4].ciFailedSha, 'deadbeef');
  assert.equal(s.prs[4].handled, undefined);
});

test('ack of an address-review item that is not pending is refused', () => {
  assert.throws(() => ack({ version: 1, prs: {} }, '3.address-review.0123abcd'), /not pending/);
});

test('ack moves the pending event keys to handled, and the sha cursors of the other kinds', () => {
  const s = { version: 1, prs: {} };
  const id = itemId({ kind: 'address-review', pr: 12, cursor: digest(['review:1', 'comment:2']) });
  setPending(s, 12, { [id]: ['review:1', 'comment:2'] });
  ack(s, id);
  assert.ok(isHandled(s.prs[12], 'review:1') && isHandled(s.prs[12], 'comment:2'));
  assert.equal(s.prs[12].pending?.[id], undefined, 'no longer pending');
  assert.throws(() => ack(s, id), /not pending/, 'a second ack is refused');
  assert.equal(s.prs[12].reviewedSha, undefined);
  ack(s, itemId({ kind: 'review', pr: 12, cursor: 'abc123' }));
  assert.equal(s.prs[12].reviewedSha, 'abc123');
  setPending(s, 12, {});
  assert.equal(s.prs[12].pending, undefined);
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
  assert.equal(acquireLock(dir, { now: () => t0 + STALE_LOCK_MS }), null, 'exactly the threshold is not stale');
  const stolen = acquireLock(dir, { now: () => t0 + STALE_LOCK_MS + 1 });
  assert.ok(stolen, 'a lock older than 30 minutes is replaced');
  releaseLock(stolen);
  assert.ok(acquireLock(dir, { now: () => t0 }), 'released lock can be taken again');
  assert.equal(STALE_LOCK_MS, 30 * 60 * 1000);
});

test('a runner whose lock was taken over does not release the new owner', () => {
  const dir = tmp();
  const t0 = Date.parse('2026-11-21T12:00:00Z');
  const old = acquireLock(dir, { now: () => t0 });
  const fresh = acquireLock(dir, { now: () => t0 + STALE_LOCK_MS + 1 });
  assert.ok(fresh);
  releaseLock(old);
  assert.equal(acquireLock(dir, { now: () => t0 + STALE_LOCK_MS + 2 }), null, 'the new owner still holds the lock');
  releaseLock(fresh);
  assert.ok(acquireLock(dir, { now: () => t0 }));
});

test('refreshLock keeps a long run from looking stale', () => {
  const dir = tmp();
  const t0 = Date.parse('2026-11-21T12:00:00Z');
  const h = acquireLock(dir, { now: () => t0 });
  refreshLock(h, { now: () => t0 + STALE_LOCK_MS });
  assert.equal(acquireLock(dir, { now: () => t0 + STALE_LOCK_MS + 2 }), null);
});

test('a lock with an unreadable owner falls back to the directory time', () => {
  const dir = tmp();
  fs.mkdirSync(path.join(dir, 'lock'));
  fs.writeFileSync(path.join(dir, 'lock', 'owner.json'), '{}');
  assert.equal(acquireLock(dir, { now: () => Date.now() }), null, 'a fresh lock directory is not stale');
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
  assert.equal(capReached(0, NaN), true, 'a bad limit stops instead of turning the cap off');
});
