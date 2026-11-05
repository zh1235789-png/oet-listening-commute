// 再生エンジン：1文ずつ止まる／くり返して次へ／通し／⭐の順再生。
// 音声要素は偽物を使い、currentTime を進めて onTick() を呼ぶ。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadApp } from './harness.mjs';

const TODAY = '2026-11-06T08:00:00+09:00';

function setup(mode, extra = {}) {
  const app = loadApp({ today: TODAY });
  const au = {
    currentTime: 0, paused: true, muted: false, playbackRate: 1, defaultPlaybackRate: 1,
    play() { this.paused = false; return Promise.resolve(); },
    pause() { this.paused = true; },
  };
  app.document = {
    querySelector: (s) => (s === '#au' ? au : null),
    querySelectorAll: () => [],
    documentElement: { style: { setProperty() {} } },
    createElement: () => ({ style: {} }),
    body: { appendChild() {} },
  };
  app.setInterval = () => 1; // タイマーは手で回す
  app.clearInterval = () => {};
  app.$(`setData({ k: '', tests: [{ id: 't3', title: 'Sample Test 1', group: 'g', tracks: [
    { id: 't3a', label: 'Part A', part: 'A', dur: 30, size: 1, sha: 'x', sents: [[1, 3, 'one.'], [4, 6, 'two.'], [8, 10, 'three.']] },
    { id: 't3b', label: 'Part B', part: 'B', dur: 30, size: 1, sha: 'x', sents: [[2, 5, 'bee.']] } ] }] })`);
  app.$(`P.tr = TRACKS.t3a; P.url = 'blob:x'; LOCK.state = 'open'`);
  app.$(`S.set.mode = '${mode}'`);
  for (const [k, v] of Object.entries(extra)) app.$(`S.set.${k} = ${JSON.stringify(v)}`);
  const tick = (t) => { au.currentTime = t; app.$('onTick()'); };
  return { app, au, tick };
}

test('1文ずつ：文の終わりで止まり、次の文へは進まない', () => {
  const { app, au, tick } = setup('step');
  app.$('playSent(0)');
  assert.equal(au.currentTime, 1);
  assert.equal(au.paused, false);
  tick(2.5);
  assert.equal(au.paused, false);
  tick(3.05);
  assert.equal(au.paused, true);
  assert.equal(app.$('P.i'), 0);
  assert.equal(app.$('S.pos.t3a'), 0);
  app.$('next()');
  assert.equal(au.currentTime, 4);
  assert.equal(app.$('P.i'), 1);
  assert.equal(app.$('S.far.t3a'), 1);
});

test('もう1回：同じ文の頭に戻る', () => {
  const { app, au, tick } = setup('step');
  app.$('playSent(1)');
  tick(6.1);
  app.$('again()');
  assert.equal(au.currentTime, 4);
  assert.equal(au.paused, false);
});

test('くり返し×2：同じ文を2回、間はミュートで再生を続け、そのあと次の文へ', () => {
  const { app, au, tick } = setup('repeat', { reps: 2, gap: 1 });
  app.$('playSent(0)');
  tick(3.0);                      // 1回目の終わり → 間（2秒）
  assert.equal(app.$('P.gapping'), true);
  assert.equal(au.muted, true);
  assert.equal(au.paused, false, '間でも止めない（ロック中にページが眠らないように）');
  tick(4.5);                      // 間の途中：まだ戻らない
  assert.equal(app.$('P.gapping'), true);
  tick(5.0);                      // 間が終わる → 同じ文をもう一度
  assert.equal(au.currentTime, 1);
  assert.equal(au.muted, false);
  assert.equal(app.$('P.i'), 0);
  tick(3.0);                      // 2回目の終わり → 間
  tick(5.0);                      // → 次の文
  assert.equal(app.$('P.i'), 1);
  assert.equal(au.currentTime, 4);
});

test('くり返し：最後の文を言い終えたら止まる', () => {
  const { app, au, tick } = setup('repeat', { reps: 2 });
  app.$('playSent(2)');
  tick(10); tick(20);             // 1回目 → 間 → 2回目
  assert.equal(au.currentTime, 8);
  tick(10);
  assert.equal(au.paused, true);
  assert.equal(app.$('P.gapping'), false);
});

test('くり返し：間の途中でファイルが終わっても次へ進む', () => {
  const { app, au, tick } = setup('repeat', { reps: 2 });
  app.$('playSent(0)');
  tick(3);
  app.$('onEnded()');
  assert.equal(au.currentTime, 1);
  assert.equal(au.muted, false);
});

test('通し：止まらず、今の文の番号だけ追いかける', () => {
  const { app, au, tick } = setup('flow');
  app.$('playSent(0)');
  tick(3.2);
  assert.equal(au.paused, false);
  tick(4.2);
  assert.equal(app.$('P.i'), 1);
  tick(9);
  assert.equal(app.$('P.i'), 2);
  assert.equal(app.$('S.far.t3a'), 2);
});

test('速さを変えても間は実時間で同じ長さ（再生速度ぶん先まで進める）', () => {
  const { app, au, tick } = setup('repeat', { reps: 2, gap: 1, speed: 0.75 });
  app.$('playSent(0)');
  au.playbackRate = 0.75;
  tick(3.0);
  // 文2秒 ÷ 0.75 = 実時間2.67秒の間 → 音声上は 2.67 × 0.75 = 2秒先
  assert.ok(Math.abs(app.$('P.gapUntil') - 5.0) < 0.01, String(app.$('P.gapUntil')));
});

test('⭐を順に再生：別トラックの⭐にも移る', async () => {
  const { app, au } = setup('step');
  app.$(`toggleStar(TRACKS.t3a, 1); toggleStar(TRACKS.t3b, 0)`);
  assert.equal(app.$('starList().length'), 2);
  await app.$('playQueue(0)');
  assert.equal(app.$('P.i'), 1);
  // 別トラックへ：openTrack は音声の取得を試みる → テストでは開けずに止まるが、落ちないこと
  app.$('fetchAudio = async () => { throw new Error("offline"); }');
  await app.$('nextInQueue()');
  assert.equal(app.$('P.qi'), 1);
  assert.equal(typeof au.currentTime, 'number');
});
