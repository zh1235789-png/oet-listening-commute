"""公開用ファイルを作る。

  python3 build/build.py             # 全トラックがそろっている時
  python3 build/build.py --partial   # 文字起こしの途中でも、できた分だけ公開する

  入力: 圧縮音声 ~/.cache/oet-listening-commute/m4a/<id>.m4a（prepare.py が作る）
        文字起こし iCloud 英語学習/OET/Listening通勤_非公開/transcripts/<id>.json
  出力: a/<id>.bin       音声を AES-GCM で暗号化したもの（先頭12バイトがIV）
        data.enc.json    一覧・スクリプト・音声の鍵を合言葉で暗号化したもの
        index.html       APP_VERSION を更新

音声の鍵 ~/.config/oet-listening-commute/audio.key は初回に作り、以後同じものを使う。
IV は音声の中身から決めるので、音声が変わらなければ .bin も変わらない（git が毎回200MB増えないように）。
合言葉は Reading通勤ドリルと同じファイルを使う（中身はこのスクリプトだけが読む）。
"""
import base64
import hashlib
import hmac
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from catalog import CACHE, PRIVATE, scan  # noqa: E402
from segment import segment  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONF = Path.home() / '.config/oet-listening-commute'
PASS_FILES = [os.environ.get('OET_PASS_FILE'), CONF / 'passphrase', Path.home() / '.config/oet-reading-commute/passphrase']
PARTIAL = '--partial' in sys.argv
MIN_WPM = 60  # 普通のトラックは 96〜156語/分
ITERATIONS = 200_000  # Reading通勤ドリル・デイリーホームと同じ（PBKDF2-SHA256 → AES-GCM 256bit）


def b(x):
    return base64.b64encode(x).decode()


def audio_key():
    f = CONF / 'audio.key'
    if not f.exists():
        CONF.mkdir(parents=True, exist_ok=True)
        f.write_bytes(os.urandom(32))
        f.chmod(0o600)
    k = f.read_bytes()
    assert len(k) == 32
    return k


def passphrase():
    for p in PASS_FILES:
        if p and Path(p).exists():
            s = Path(p).read_text(encoding='utf-8').strip()
            if len(s) < 8:
                raise SystemExit('合言葉が短すぎます（8文字以上）')
            return s
    raise SystemExit('合言葉のファイルがありません: ~/.config/oet-listening-commute/passphrase')


def encrypt_audio(key, data):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    iv = hmac.new(key, hashlib.sha256(data).digest(), 'sha256').digest()[:12]
    return iv + AESGCM(key).encrypt(iv, data, None)


def encrypt_json(obj, pw):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(hashes.SHA256(), 32, salt, ITERATIONS).derive(pw.encode())
    ct = AESGCM(key).encrypt(iv, json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode(), None)
    return {'v': 1, 'iter': ITERATIONS, 'salt': b(salt), 'iv': b(iv), 'ct': b(ct)}


def main():
    key, pw = audio_key(), passphrase()
    (ROOT / 'a').mkdir(exist_ok=True)
    tests, missing, thin = [], [], []
    for t in scan():
        tracks = []
        for tr in t['tracks']:
            m4a = CACHE / 'm4a' / f"{tr['id']}.m4a"
            tj = PRIVATE / 'transcripts' / f"{tr['id']}.json"
            if not (m4a.exists() and tj.exists()):
                missing.append(tr['id'])
                continue
            raw = m4a.read_bytes()
            enc = encrypt_audio(key, raw)
            out = ROOT / 'a' / f"{tr['id']}.bin"
            if not out.exists() or out.read_bytes() != enc:
                out.write_bytes(enc)
            d = json.loads(tj.read_text(encoding='utf-8'))
            sents = segment(d['words'], d.get('dur'))
            if not sents:
                raise SystemExit(f"{tr['id']}: 文が0件")
            wpm = len(d['words']) / (d['dur'] / 60)
            if wpm < MIN_WPM:  # 文字起こしの取りこぼし（Test 15 は音量が小さく 0〜22語/分だった）
                thin.append(f"{tr['id']}({wpm:.0f}語/分)")
            tracks.append({'id': tr['id'], 'label': tr['label'], 'part': tr['part'], 'dur': round(d['dur'], 1),
                           'size': len(enc), 'sha': hashlib.sha256(enc).hexdigest()[:10], 'sents': sents})
        if tracks:
            tests.append({'id': t['id'], 'title': t['title'], 'group': t['group'], 'tracks': tracks})
    if thin:
        raise SystemExit(f'文字起こしの語数が少なすぎるトラックがあります: {" ".join(thin)}。'
                         'prepare.py <id> で作り直してから公開する')
    if missing and not PARTIAL:
        raise SystemExit(f'音声か文字起こしが無いトラックが{len(missing)}件あります（{" ".join(missing[:8])}…）。'
                         '途中のまま公開するなら --partial を付ける')
    # 消すのは一覧から外れたトラックの .bin だけ。入力が一時的に読めないだけで公開中の音声を消さない
    known = {tr['id'] + '.bin' for t in scan() for tr in t['tracks']}
    for f in (ROOT / 'a').glob('*.bin'):
        if f.name not in known:
            f.unlink()
    env = encrypt_json({'k': b(key), 'tests': tests}, pw)
    (ROOT / 'data.enc.json').write_text(json.dumps(env, separators=(',', ':')), encoding='utf-8')

    ver = datetime.now(timezone(timedelta(hours=9))).strftime('%Y.%m.%d-%H%M')
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    html, n = re.subn(r"const APP_VERSION = '[^']*';", f"const APP_VERSION = '{ver}';", html)
    assert n == 1, 'APP_VERSION が見つからない'
    (ROOT / 'index.html').write_text(html, encoding='utf-8')

    n_tr = sum(len(t['tracks']) for t in tests)
    n_s = sum(len(tr['sents']) for t in tests for tr in t['tracks'])
    size = sum(tr['size'] for t in tests for tr in t['tracks'])
    print(f'{len(tests)}テスト・{n_tr}トラック・{n_s}文・音声{size/1e6:.0f}MB  v{ver}')
    if missing:
        print(f'未処理（音声か文字起こしが無い）{len(missing)}件: {" ".join(missing)}')


if __name__ == '__main__':
    main()
