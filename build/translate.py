"""スクリプトの各文に和訳を付ける（英文表示をタップしたとき英文の下に出す）。

  python3 build/translate.py          # 和訳がまだ無い文だけ
  python3 build/translate.py t3a      # 指定トラックだけ

訳は Claude Code（claude -p, Sonnet）でトラック単位に作る（前後の文脈を見て訳せるように）。
出力: iCloud 英語学習/OET/Listening通勤_非公開/ja.json  {英文: 和訳}
英文をキーにするので、文の区切りを作り直しても同じ英文の訳はそのまま使える。
build.py がこれを読み、各文の4番目の要素として暗号化データに入れる。
"""
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
from catalog import PRIVATE, scan  # noqa: E402
from segment import segment  # noqa: E402

JA = PRIVATE / 'ja.json'
WORKERS = 4
LOCK = threading.Lock()

PROMPT = """これは医療英語試験 OET Listening の音声（{kind}）を自動で文字起こしし、文に区切ったものです。
各行の英文を、日本の医師が読んで自然な日本語に訳してください。

- 話し言葉は話し言葉らしく（医師は丁寧語、患者は普通の口調）
- 医学用語は日本の医療現場の言い方にする（例: shortness of breath → 息切れ、GP → かかりつけ医）
- 文字起こしの誤りや文の切れ端も、前後の文脈から意味をくんで訳す。補足や注釈は付けない
- 出力は JSON の文字列配列だけ。要素数は入力の行数（{n}）とちょうど同じにし、順番も同じにする

{lines}"""

KIND = {'A': '診察の会話。受験者はメモを埋める', 'B': '医療現場の短い会話や説明',
        'C': '医療者へのインタビューや講演', '': '模試'}


def load():
    try:
        return json.loads(JA.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}


def save(d):
    tmp = JA.with_suffix('.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding='utf-8')
    tmp.replace(JA)


def ask(texts, part):
    lines = '\n'.join(f'{i + 1}. {t}' for i, t in enumerate(texts))
    prompt = PROMPT.format(kind=KIND.get(part, KIND['']), n=len(texts), lines=lines)
    # 本人の設定（フック等）は読まない。セッション記録にも残さない
    r = subprocess.run(['claude', '-p', '--model', 'sonnet', '--setting-sources', 'project',
                        '--no-session-persistence', '--tools='],
                       input=prompt, capture_output=True, text=True, timeout=600, cwd=PRIVATE)
    out = r.stdout.strip()
    s, e = out.find('['), out.rfind(']')
    try:
        arr = json.loads(out[s:e + 1])
    except ValueError:
        return None
    if len(arr) != len(texts) or not all(isinstance(x, str) and x.strip() for x in arr):
        return None
    return [x.strip() for x in arr]


def translate(texts, part):
    """数が合わなければ半分に割ってやり直す。"""
    for _ in range(2):
        arr = ask(texts, part)
        if arr:
            return arr
    if len(texts) <= 3:
        raise RuntimeError(f'訳せない: {texts}')
    h = len(texts) // 2
    return translate(texts[:h], part) + translate(texts[h:], part)


def main():
    only = set(sys.argv[1:])
    ja = load()
    jobs = []
    for t in scan():
        for tr in t['tracks']:
            if only and tr['id'] not in only:
                continue
            tj = PRIVATE / 'transcripts' / f"{tr['id']}.json"
            if not tj.exists():
                continue
            d = json.loads(tj.read_text(encoding='utf-8'))
            texts = [s[2] for s in segment(d['words'], d.get('dur'), drop=True)]
            if any(x not in ja for x in texts):
                jobs.append((tr['id'], tr['part'], texts))
    print(f'和訳するトラック: {len(jobs)}件', flush=True)
    fails = []

    def run(job):
        tid, part, texts = job
        try:
            arr = []
            for i in range(0, len(texts), 60):  # 長いトラックは60文ずつ（文脈は保ちつつ出力の取りこぼしを防ぐ）
                arr += translate(texts[i:i + 60], part)
        except Exception as ex:  # noqa: BLE001
            fails.append(tid)
            print(f'{tid}: 失敗 {ex}', flush=True)
            return
        with LOCK:
            ja.update(zip(texts, arr))
            save(ja)
        print(f'{tid}: {len(texts)}文', flush=True)

    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(run, jobs))
    print(f'完了。和訳 {len(ja)}文' + (f'／失敗 {" ".join(fails)}' if fails else ''))
    if fails:
        sys.exit(1)


if __name__ == '__main__':
    main()
