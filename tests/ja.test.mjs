// 和訳：英文を表示したときだけ英文の下に出る。和訳の無い文は英文だけ。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadApp } from './harness.mjs';

function setup(show) {
  const app = loadApp({ today: '2026-11-11T08:00:00+09:00' });
  app.$(`setData({ k: '', tests: [{ id: 't3', title: 'Sample Test 1', group: 'g', tracks: [
    { id: 't3a', label: 'Part A', part: 'A', dur: 30, size: 1, sha: 'x',
      sents: [[1, 3, 'Any pain?', '痛みはありますか？'], [4, 6, 'No <b>.']] } ] }] })`);
  app.$(`S.set.show = '${show}'; UI.peek = null`);
  return app;
}

test('隠している間は英文も和訳も出ない', () => {
  const app = setup('hide');
  const h = app.$('sentInner(TRACKS.t3a, 0)');
  assert.ok(!h.includes('Any pain?'));
  assert.ok(!h.includes('痛みはありますか'));
});

test('タップで表示すると英文の下に和訳が出る', () => {
  const app = setup('hide');
  app.$('UI.peek = 0');
  const h = app.$('sentInner(TRACKS.t3a, 0)');
  assert.ok(h.indexOf('Any pain?') < h.indexOf('<div class="ja">痛みはありますか？</div>'));
});

test('和訳の無い文は英文だけ（エスケープも保つ）', () => {
  const app = setup('always');
  const h = app.$('sentInner(TRACKS.t3a, 1)');
  assert.ok(h.includes('No &lt;b&gt;.'));
  assert.ok(!h.includes('class="ja"'));
});

test('⭐ 復習の一覧でも、ぼかしの中に和訳が入る', () => {
  const app = setup('hide');
  app.$(`toggleStar(TRACKS.t3a, 0)`);
  const h = app.$('reviewView()');
  assert.match(h, /class="t blur" data-reveal>Any pain\?<span class="ja">痛みはありますか？<\/span><\/span>/);
});
