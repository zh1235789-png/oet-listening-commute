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
        segs, info = model.transcribe(str(m4a), language='en', word_timestamps=True, vad_filter=True,
                                      beam_size=5, condition_on_previous_text=False)
        words = [[round(w.start, 2), round(w.end, 2), w.word] for s in segs for w in s.words]
        data = {'id': tr['id'], 'model': MODEL, 'dur': round(info.duration, 2), 'words': words}
        tmp = out.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        tmp.rename(out)
        print(f"[{i}/{len(tracks)}] {tr['id']} {info.duration/60:.1f}分 → {time.time()-t0:.0f}秒, {len(words)}語", flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main(set(sys.argv[1:]))
