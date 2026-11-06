"""単語単位の時刻つき文字起こしを「文」に区切る。

区切る条件:
  - 語が . ? ! で終わり、文が3語以上（Dr. Mr. などの略語は除く）
  - 次の語までの無音が 1.2秒以上
  - 文が 18秒を超え、語がカンマ等で終わる（長すぎる文は聞き返しにくい）
各文の開始は 0.15秒早め、終了は 0.3秒遅め（前後の文とは重ならない範囲で）。

drop_instructions() は試験の指示文（Now read the question. / You now have 90 seconds ... など）を除く。
場面の説明（You hear a nurse talking to ...）は誰が話すかが分かるので残す。
本文を誤って消さないよう、文全体が指示文の決まった形だけでできている時だけ除く。
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


N = r'(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|[a-z]{3,9}(?:-[a-z]+)?)'
R = r' (?:to|and|-) '
_INSTR = [
    r'(?:now,? )?read the questions?',
    r'(?:now,? )?answer questions? ' + N,
    r'(?:now,? )?(?:turn over and )?look at (?:the notes for |your notes for )?(?:extract|question) ' + N + r'(?:[.,]? questions? ' + N + R + N + r')?',
    r'(?:now,? )?(?:turn over and )?look at part [abc]',
    r'(?:now,? )?(?:turn over and )?look at (?:the|your) notes(?: for extract ' + N + r')?',
    r'question ' + N,
    r'(?:extract|part) (?:' + N + r'|[abc])[.,]? questions? ' + N + R + N,
    r'questions? ' + N + R + N,
    r'extract ' + N,
    r'part [abc]',
    r'(?:you|we) (?:now )?(?:have|will have|\'ll have) ' + N + r' (?:seconds|minutes?) to (?:read|look|check|transfer)[^.?!]*',
    r'for (?:the )?questions?(?: below| ' + N + r'(?:' + R.replace(' ', ' ?') + N + r')?)?,? (?:complete|choose|answer)[^.?!]*',
    r'answer the questions below[^.?!]*',
    r'complete your answers as you listen',
    r'(?:that )?is the end of (?:listening )?(?:part [abc]|the listening test|the test)',
    r'in this part of the test,? you(?:\'ll| will) hear[^.?!]*',
    r'in each (?:extract|part),? (?:you(?:\'ll| will) hear|a health professional is talking)[^.?!]*',
    r'at the start of each extract,? you(?:\'ll| will) hear this sound',
    r'you(?:\'ll| will) have time to read (?:the|each) questions?[^.?!]*',
    r'(?:and )?you(?:\'ll| will) hear each extract once only',
    r'at the end of the test,? you(?:\'ll| will) have[^.?!]*',
    r'remember,? while you(?:\'re| are) listening[^.?!]*',
    r'i(?:\'ll| will) introduce each part of the test[^.?!]*',
    r'(?:this is|welcome to) (?:the )?oet[^.?!]*listening[^.?!]*',
]
_INSTR_RE = re.compile(r'(?:' + '|'.join(_INSTR) + r')[.?!,]?\s*', re.I)


def is_instruction(text):
    t = text.strip()
    pos = 0
    while pos < len(t):
        m = _INSTR_RE.match(t, pos)
        if not m or m.end() == pos:
            return False
        pos = m.end()
    return bool(t)


def drop_instructions(sents):
    return [s for s in sents if not is_instruction(s[2])]


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
