// 文の位置・⭐の付け直し・記録の取り込み・聞いた時間の集計
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadApp, norm } from './harness.mjs';

const TODAY = '2026-11-06T08:00:00+09:00';
const SENTS = [[0.5, 3.2, 'One two three.'], [3.4, 7.9, 'Four five six.'], [10, 14, 'Seven eight nine.']];

test('sentAt: 時刻を含む文、文と文の間なら直前の文', () => {
  const app = loadApp({ today: TODAY });
  const at = app.$('sentAt');
  app.SENTS = SENTS;
  assert.equal(app.$('sentAt(SENTS, 0)'), 0);
  assert.equal(at(SENTS, 3.3), 0);
  assert.equal(at(SENTS, 3.4), 1);
  assert.equal(at(SENTS, 9.0), 1);
  assert.equal(at(SENTS, 99), 2);
});

test('⭐は開始時刻で覚え、文の区切りを作り直しても近い文に付き直す', () => {
  const app = loadApp({ today: TODAY });
  const key = app.$('starKey')('t3a', SENTS[1]);
  assert.equal(key, 't3a@34');
  const tr = { id: 't3a', sents: [[0.4, 3.0, 'a'], [3.2, 5.5, 'b'], [5.6, 7.9, 'c'], [10, 14, 'd']] };
  assert.equal(app.$('findStarSent')(tr, key), 1);
  // 3秒より離れた文しか無ければ付けない（別物に付くより消える方がまし）
  assert.equal(app.$('findStarSent')({ id: 't3a', sents: [[20, 25, 'x']] }, key), -1);
});

test('日付は日本時間で切る（朝7時台は当日、前夜23時は前日）', () => {
  const app = loadApp({ today: TODAY });
  const k = app.$('todayKey');
  assert.equal(k(new Date('2026-11-06T07:30:00+09:00')), '2026-11-06');
  assert.equal(k(new Date('2026-11-05T23:30:00+09:00')), '2026-11-05');
  assert.equal(k(new Date('2026-11-06T00:10:00+09:00')), '2026-11-06');
});

test('取り込みは上書きでなく合わせる', () => {
  const app = loadApp({ today: TODAY });
  const cur = { v: 1, pos: { t3a: 5 }, far: { t3a: 10, t3b: 2 }, stars: { 't3a@34': { ts: 1 } }, days: { '2026-11-05': 300 }, set: {} };
  const inc = { pos: { t3a: 1, t4a: 3 }, far: { t3a: 4, t3b: 9 }, stars: { 't4a@100': { ts: 2 } }, days: { '2026-11-05': 100, '2026-11-04': 50 } };
  const out = norm(app.$('mergeState')(cur, inc));
  assert.deepEqual(Object.keys(out.stars).sort(), ['t3a@34', 't4a@100']);
  assert.deepEqual(out.far, { t3a: 10, t3b: 9 });
  assert.deepEqual(out.pos, { t3a: 5, t4a: 3 });
  assert.deepEqual(out.days, { '2026-11-05': 300, '2026-11-04': 50 });
});

test('関係ないJSONは取り込まない', () => {
  const app = loadApp({ today: TODAY });
  assert.equal(norm(app.$('importJson')('not json')).ok, false);
  assert.equal(norm(app.$('importJson')('{"foo":1}')).ok, false);
  const ok = norm(app.$('importJson')(JSON.stringify({ app: 'oet-listening-commute', state: { stars: { 'x@1': { ts: 1 } } } })));
  assert.equal(ok.ok, true);
  assert.equal(ok.stars, 1);
});

test('7日間の合計は今日を含む直近7日', () => {
  const app = loadApp({ today: TODAY });
  app.$(`S.days = {'2026-11-06': 600, '2026-10-31': 120, '2026-10-30': 999}`);
  assert.equal(app.$('weekSeconds()'), 720);
});

test('聞いた時間：40ミリ秒ごとの細かい加算でも積み上がる（丸めで0にならない）', () => {
  const app = loadApp({ today: TODAY });
  const au = { paused: false };
  app.document = { querySelector: (s) => (s === '#au' ? au : null) };
  let now = 1_000_000;
  app.Date = class extends Date { static now() { return now; } constructor(...a) { if (a.length) super(...a); else super(TODAY); } };
  for (let i = 0; i <= 250; i++) { app.$('tickListen()'); now += 40; }
  const sec = app.$(`S.days['2026-11-06']`);
  assert.ok(sec > 9.9 && sec < 10.1, String(sec));
  au.paused = true; app.$('tickListen()'); now += 5000; au.paused = false; app.$('tickListen()'); now += 40; app.$('tickListen()');
  assert.ok(app.$(`S.days['2026-11-06']`) < 10.2, '止めている間は数えない');
});
