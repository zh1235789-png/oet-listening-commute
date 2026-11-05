// index.html が起動時に例外を出さないことの回帰テスト。
// 純粋関数のテストは関数定義さえあれば通るため、これが無いと
// 「起動した瞬間に落ちるアプリ」を緑のまま見逃す。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { assertLoads } from './harness.mjs';

const TODAY = '2026-11-06T08:00:00+09:00';

test('index.html が例外なく初期化できる', () => {
  assertLoads({ today: TODAY });
});

test('保存データが空でも初期化できる（初回起動）', () => {
  const app = assertLoads({ today: TODAY, storage: {} });
  assert.equal(app.$('LOCK.state'), 'locked');
  assert.equal(app.$('S.set.mode'), 'step');
});

test('保存データが壊れていても初期化できる', () => {
  const junk = { __proto__: null };
  assertLoads({ today: TODAY, storage: new Proxy(junk, { get: () => 'not json{' }) });
});

test('設定値がおかしくても既定値に戻して起動する', () => {
  const bad = JSON.stringify({ v: 1, pos: 'x', stars: null, set: { mode: 'zzz', speed: 9, gap: -1, reps: 99, show: 1 } });
  const app = assertLoads({ today: TODAY, storage: { 'oet-listening-commute-v1': bad } });
  assert.equal(app.$('S.set.mode'), 'step');
  assert.equal(app.$('S.set.speed'), 1);
  assert.equal(app.$('S.set.gap'), 0.5);
  assert.equal(app.$('S.set.reps'), 2);
  assert.equal(app.$('S.set.show'), 'after');
  assert.equal(typeof app.$('S.stars'), 'object');
});

test('合言葉が保存済みでも、圏外（fetch失敗）で落ちない', async () => {
  const app = assertLoads({ today: TODAY, storage: { 'oet-listening-commute-pass': 'whatever-pass' } });
  await new Promise((r) => setTimeout(r, 20));
  assert.equal(app.$('LOCK.state'), 'locked');
  assert.match(app.$('LOCK.err'), /読めません/);
});

test('localStorage 自体が例外を投げても起動する（プライベートブラウズ）', () => {
  const app = assertLoads({ today: TODAY });
  app.localStorage.getItem = () => { throw new Error('denied'); };
  app.localStorage.setItem = () => { throw new Error('denied'); };
  app.$('S = loadState()');
  app.$('save()');
  assert.equal(app.$('LS.ok'), false);
});
