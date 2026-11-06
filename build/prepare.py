"""音源を圧縮（モノラルAAC 32kbps）し、Whisper で単語単位の時刻つき文字起こしを作る。

  ~/whisper-env/bin/python build/prepare.py            # 未処理のものだけ
  ~/whisper-env/bin/python build/prepare.py t3a t3b    # 指定のものだけ（作り直し）

出力（どちらも公開リポジトリには入れない）:
  圧縮音声   ~/.cache/oet-listening-commute/m4a/<id>.m4a
  文字起こし iCloud 英語学習/OET/Listening通勤_非公開/transcripts/<id>.json
文字起こしは圧縮後の m4a から取る（アプリで再生する音と時刻を一致させるため）。
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from catalog import CACHE, PRIVATE, scan  # noqa: E402

MODEL = os.environ.get('OET_WHISPER_MODEL', 'medium.en')


def compress(src, dst):
    tmp = dst.with_suffix('.tmp.m4a')
    subprocess.run(['afconvert', str(src), str(tmp), '-f', 'm4af', '-d', 'aac@22050', '-b', '32000', '-c', '1'], check=True)
    tmp.rename(dst)


QUIET_DB = -26    # これより小さい音源は持ち上げる（Test 15 は -34〜-38dB で、無音フィルターが声ごと消していた）
TARGET_DB = -20
MIN_WPM = 60      # 1分あたりの語数がこれ未満なら取りこぼしとみなし、無音フィルターなしでやり直す（普通は96〜156）


def _db(x):
    import numpy as np
    return float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9))


def hallucinated(s):
    """無音フィルターなしの時、黙読時間などに出る幻の文字（No, no, no… など）を見分ける。"""
    ws = [w.word.strip(' .,!?').lower() for w in (s.words or [])]
    if s.compression_ratio > 2.4:
        return True
    if len(ws) >= 4 and max(ws.count(w) for w in set(ws)) / len(ws) > 0.5:
        return True
    return s.no_speech_prob > 0.6 and s.avg_logprob < -0.5


def transcribe(model, m4a):
    """返り値: (words, 長さ秒, ログ用の注記)"""
    import numpy as np
    from faster_whisper.audio import decode_audio
    a = decode_audio(str(m4a))
    dur = len(a) / 16000
    note = ''
    level = _db(a)
    if level < QUIET_DB:
        a = np.clip(a * 10 ** ((TARGET_DB - level) / 20), -1, 1).astype(np.float32)
        note += f'（音量{level:.0f}dB→持ち上げ）'
    opts = dict(language='en', word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    segs = list(model.transcribe(a, vad_filter=True, **opts)[0])
    if sum(len(s.words or []) for s in segs) < MIN_WPM * dur / 60:
        segs = [s for s in model.transcribe(a, vad_filter=False, **opts)[0] if not hallucinated(s)]
        note += '（無音フィルターなしでやり直し）'
    words = [[round(w.start, 2), round(w.end, 2), w.word] for s in segs for w in (s.words or [])]
    if len(words) < MIN_WPM * dur / 60:
        note += ' ⚠️語数が少ない'
    return words, dur, note


def main(only):
    (CACHE / 'm4a').mkdir(parents=True, exist_ok=True)
    (PRIVATE / 'transcripts').mkdir(parents=True, exist_ok=True)
    tracks = [tr for t in scan() for tr in t['tracks']]
    if only:
        tracks = [tr for tr in tracks if tr['id'] in only]
    model = None
    for i, tr in enumerate(tracks, 1):
        m4a = CACHE / 'm4a' / f"{tr['id']}.m4a"
        out = PRIVATE / 'transcripts' / f"{tr['id']}.json"
        if not m4a.exists() or only:
            compress(tr['src'], m4a)
        if out.exists() and not only:
            continue
        if model is None:
            from faster_whisper import WhisperModel
            model = WhisperModel(MODEL, device='cpu', compute_type='int8', cpu_threads=os.cpu_count())
        t0 = time.time()
        words, dur, note = transcribe(model, m4a)
        data = {'id': tr['id'], 'model': MODEL, 'dur': round(dur, 2), 'words': words}
        tmp = out.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        tmp.rename(out)
        print(f"[{i}/{len(tracks)}] {tr['id']} {dur/60:.1f}分 → {time.time()-t0:.0f}秒, {len(words)}語{note}", flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main(set(sys.argv[1:]))
