"""音源フォルダ（iCloud 英語学習/OET/公式ガイド・模試/Audio）から、テストとトラックの一覧を作る。

ID はフォルダ番号とパート名から決める（表示名から作らない）。
  "20- OET Online Test 6/20-Part A.mp3"                  → t20a
  "1- Kaplan Startegies and Practice Set/Part B/Track 9" → t1-09
  "2- Kaplan Practice Test/Track 21.mp3"                 → t2
"""
import os
import re
from pathlib import Path

OET = Path.home() / 'Library/Mobile Documents/com~apple~CloudDocs/英語学習/OET'
AUDIO_DIR = Path(os.environ.get('OET_AUDIO_DIR') or OET / '公式ガイド・模試/Audio')
PRIVATE = Path(os.environ.get('OET_LC_PRIVATE') or OET / 'Listening通勤_非公開')
CACHE = Path(os.environ.get('OET_LC_CACHE') or Path.home() / '.cache/oet-listening-commute')

# 表示順とグループ（フォルダ番号 → グループ）
GROUPS = [
    ('公式 Sample Test', [3, 4, 26]),
    ('Practice Test', [5, 6, 7, 9]),
    ('OET Online Test', [15, 16, 17, 18, 19, 20]),
    ('E2Language', [10, 11, 12, 13, 14]),
    ('IRS', [21, 22, 23, 24, 25]),
    ('Kaplan', [2, 1]),
]
TITLE_FIX = {'Startegies': 'Strategies'}


def _title(folder):
    t = re.sub(r'^\d+-\s*', '', folder).strip()
    for a, b in TITLE_FIX.items():
        t = t.replace(a, b)
    return t


def scan():
    """[{id, title, group, tracks:[{id, label, part, src}]}] を表示順で返す。"""
    folders = {}
    for d in AUDIO_DIR.iterdir():
        m = re.match(r'^(\d+)-', d.name)
        if d.is_dir() and m:
            folders[int(m.group(1))] = d
    tests = []
    for group, nums in GROUPS:
        for n in nums:
            d = folders.get(n)
            if not d:
                continue
            tracks = []
            for f in sorted(d.rglob('*.mp3')):
                rel = f.relative_to(d)
                pm = re.search(r'Part\s*([ABC])', str(rel), re.I)
                tm = re.search(r'Track\s*(\d+)', f.stem, re.I)
                part = pm.group(1).upper() if pm else ''
                if tm and len(list(d.rglob('*.mp3'))) > 1:
                    tid, label = f't{n}-{int(tm.group(1)):02d}', f'{part} · Track {int(tm.group(1))}'
                elif part:
                    tid, label = f't{n}{part.lower()}', f'Part {part}'
                else:
                    tid, label = f't{n}', '全パート'
                tracks.append({'id': tid, 'label': label, 'part': part, 'src': f})
            tracks.sort(key=lambda t: (t['part'], int(re.sub(r'\D', '', t['id'].split('-')[-1]) or 0) if '-' in t['id'] else 0))
            tests.append({'id': f't{n}', 'title': _title(d.name), 'group': group, 'tracks': tracks})
    return tests


if __name__ == '__main__':
    for t in scan():
        print(t['id'], t['group'], '|', t['title'], '|', ' '.join(x['id'] for x in t['tracks']))
