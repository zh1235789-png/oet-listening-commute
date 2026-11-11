// 一覧の「保存済みだけ」：保存したトラックとそのテストだけを出す。設定は覚えておく。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadApp } from './harness.mjs';

function setup() {
  const app = loadApp({ today: '2026-11-12T08:00:00+09:00' });
  app.$(`setData({ k: '', tests: [
    { id: 't3', title: 'Sample Test 1', group: 'g', tracks: [
      { id: 't3a', label: 'Part A', part: 'A', dur: 30, size: 1, sha: 'x', sents: [[1, 3, 'a.']] },
      { id: 't3b', label: 'Part B', part: 'B', dur: 30, size: 1, sha: 'x', sents: [[1, 3, 'b.']] } ] },
    { id: 't4', title: 'Sample Test 2', group: 'g', tracks: [
      { id: 't4a', label: 'Part A', part: 'A', dur: 30, size: 1, sha: 'x', sents: [[1, 3, 'c.']] } ] } ] })`);
  return app;
}

test('すべて：保存していないトラックも出る（標準）', () => {
  const app = setup();
  app.$(`SAVED = new Set(['t3a'])`);
  assert.equal(app.$('S.set.list'), 'all');
  const h = app.$('listView()');
  for (const id of ['t3a', 't3b', 't4a']) assert.ok(h.includes(`data-open="${id}"`), id);
});

test('保存済みだけ：保存したトラックと、そのテストだけ出る', () => {
  const app = setup();
  app.$(`SAVED = new Set(['t3a']); S.set.list = 'saved'`);
  const h = app.$('listView()');
  assert.ok(h.includes('data-open="t3a"'));
  assert.ok(!h.includes('data-open="t3b"'));
  assert.ok(!h.includes('Sample Test 2'));
});

test('保存済みだけで1つも無いときは案内を出す', () => {
  const app = setup();
  app.$(`SAVED = new Set(); S.set.list = 'saved'`);
  const h = app.$('listView()');
  assert.ok(h.includes('まだ保存した音源がありません'));
  assert.ok(!h.includes('data-open='));
});

test('壊れた値は「すべて」に戻す', () => {
  const app = setup();
  app.$(`LS.set(STORE_KEY, JSON.stringify({ set: { list: 'xx' } }))`);
  assert.equal(app.$('loadState().set.list'), 'all');
});
