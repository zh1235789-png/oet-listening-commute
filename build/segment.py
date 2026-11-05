"""単語単位の時刻つき文字起こしを「文」に区切る。

区切る条件:
  - 語が . ? ! で終わり、文が3語以上（Dr. Mr. などの略語は除く）
  - 次の語までの無音が 1.2秒以上
  - 文が 18秒を超え、語がカンマ等で終わる（長すぎる文は聞き返しにくい）
各文の開始は 0.15秒早め、終了は 0.3秒遅め（前後の文とは重ならない範囲で）。
"""
import re

ABBR = {'dr.', 'mr.', 'mrs.', 'ms.', 'st.', 'e.g.', 'i.e.', 'vs.', 'no.', 'approx.', 'etc.'}
GAP = 1.2
LONG = 18.0
PAD_S, PAD_E = 0.15, 0.3


def _ends_sentence(word, n_words):
    w = word.strip().lower()
    if not re.search(r'[.?!]["\')]?$', w):
        return False
    if w in ABBR or re.fullmatch(r'[a-z]\.', w):
        return False
    return n_words >= 3


def segment(words, dur=None):
    """words: [[start, end, text], ...] → [[start, end, text], ...]"""
    words = [w for w in words if w[2].strip()]
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt[0] - w[1]) if nxt else 0
        long_ = (w[1] - cur[0][0]) > LONG and re.search(r'[,;:]$', w[2].strip())
        if nxt is None or _ends_sentence(w[2], len(cur)) or gap >= GAP or long_:
            groups.append(cur)
            cur = []
    out = []
    for gi, g in enumerate(groups):
        prev_end = groups[gi - 1][-1][1] if gi else 0.0
        next_start = groups[gi + 1][0][0] if gi + 1 < len(groups) else (dur if dur else g[-1][1] + PAD_E)
        s = max(prev_end, g[0][0] - PAD_S, 0.0)
        e = min(next_start, g[-1][1] + PAD_E)
        text = re.sub(r'\s+', ' ', ''.join(w[2] for w in g)).strip()
        out.append([round(s, 2), round(max(e, s + 0.3), 2), text])
    return out


if __name__ == '__main__':
    import json
    import sys
    d = json.load(open(sys.argv[1]))
    for s, e, t in segment(d['words'], d.get('dur')):
        print(f'{s:7.2f}-{e:7.2f}  {t}')
