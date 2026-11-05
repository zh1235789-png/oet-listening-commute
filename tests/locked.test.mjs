// 暗号化した教材（音源・スクリプト）の検査。
// 1) 公開される音声ファイルが m4a のまま置かれていない
// 2) 合言葉が違うと開かない
// 3) 正しい合言葉で開くと、全トラックに文がそろい、音声が復号できて m4a になる
// 4) 公開ファイルにスクリプトが平文で入っていない
// 合言葉はリポジトリの外（この Mac）にしかないので、無い環境では 3)4) を飛ばす。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { loadApp } from './harness.mjs';

const ROOT = new URL('..', import.meta.url).pathname;
const PASS_FILES = [process.env.OET_PASS_FILE, join(homedir(), '.config/oet-listening-commute/passphrase'), join(homedir(), '.config/oet-reading-commute/passphrase')].filter(Boolean);
const PASS_FILE = PASS_FILES.find((f) => existsSync(f));
const TODAY = '2026-11-06T08:00:00+09:00';
const env = JSON.parse(readFileSync(join(ROOT, 'data.enc.json'), 'utf8'));
const bins = readdirSync(join(ROOT, 'a')).filter((f) => f.endsWith('.bin'));

function appWithData() {
  const app = loadApp({ today: TODAY });
  app.fetch = async () => ({ ok: true, json: async () => env });
  return app;
}

test('data.enc.json は暗号化の形式になっている', () => {
  assert.ok(env.ct && env.iv && env.salt && env.iter >= 100000);
});

test('公開する音声は暗号化されている（m4a の目印 ftyp が先頭に無い）', () => {
  assert.ok(bins.length > 0, '音声ファイルが無い');
  for (const f of bins) {
    const head = readFileSync(join(ROOT, 'a', f)).subarray(0, 64).toString('latin1');
    assert.ok(!head.includes('ftyp'), `${f} が平文の m4a`);
  }
});

test('合言葉が違うと開かない', async () => {
  const app = appWithData();
  assert.equal(await app.$('unlock')('wrong-passphrase', true), false);
  assert.equal(app.$('LOCK.state'), 'locked');
  assert.equal(app.$('LOCK.err'), '合言葉が違います');
});

test('正しい合言葉で開くと、全トラックに文があり、音声ファイルと1対1で対応する', { skip: !PASS_FILE && '合言葉のファイルなし' }, async () => {
  const app = appWithData();
  assert.equal(await app.$('unlock')(readFileSync(PASS_FILE, 'utf8').trim(), true), true);
  const tracks = JSON.parse(app.$('JSON.stringify(Object.values(TRACKS).map(t => ({ id: t.id, n: t.sents.length, dur: t.dur, s: t.sents })))'));
  assert.deepEqual(tracks.map((t) => t.id + '.bin').sort(), [...bins].sort());
  for (const t of tracks) {
    assert.ok(t.n > 0, `${t.id} に文が無い`);
    for (let i = 0; i < t.s.length; i++) {
      const [s, e, txt] = t.s[i];
      assert.ok(e > s && s >= 0 && e <= t.dur + 1, `${t.id} 文${i} の時刻がおかしい ${s}-${e}`);
      if (i) assert.ok(s >= t.s[i - 1][0], `${t.id} 文${i} が前の文より前`);
      assert.ok(txt.trim(), `${t.id} 文${i} が空`);
    }
  }
});

test('音声を復号すると m4a になる（先頭・途中・最後のファイル）', { skip: !PASS_FILE && '合言葉のファイルなし' }, async () => {
  const app = appWithData();
  await app.$('unlock')(readFileSync(PASS_FILE, 'utf8').trim(), true);
  const pick = [bins[0], bins[Math.floor(bins.length / 2)], bins[bins.length - 1]];
  for (const f of pick) {
    const buf = readFileSync(join(ROOT, 'a', f));
    const blob = await app.$('decryptAudio')(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length));
    const head = Buffer.from(await blob.arrayBuffer()).subarray(0, 16).toString('latin1');
    assert.ok(head.includes('ftyp'), `${f} を復号しても m4a にならない`);
  }
});

test('公開ファイルにスクリプトが平文で入っていない', { skip: !PASS_FILE && '合言葉のファイルなし' }, async () => {
  const app = appWithData();
  await app.$('unlock')(readFileSync(PASS_FILE, 'utf8').trim(), true);
  const texts = JSON.parse(app.$('JSON.stringify(Object.values(TRACKS).flatMap(t => t.sents.map(s => s[2])).filter(s => s.length >= 40).slice(0, 300))'));
  const pub = readFileSync(join(ROOT, 'index.html'), 'utf8') + readFileSync(join(ROOT, 'data.enc.json'), 'utf8');
  assert.deepEqual(texts.filter((s) => pub.includes(s.slice(0, 40))), []);
});
