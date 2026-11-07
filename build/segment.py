"""単語単位の時刻つき文字起こしを「文」に区切る。

区切る条件:
  - 語が . ? ! で終わり、文が3語以上（Dr. Mr. などの略語は除く）
  - 次の語までの無音が 1.2秒以上
  - 文が 18秒を超え、語がカンマ等で終わる（長すぎる文は聞き返しにくい）
各文の開始は 0.15秒早め、終了は 0.3秒遅め（前後の文とは重ならない範囲で）。

segment(..., drop=True) は試験のナレーション（タイトル・指示文・場面の説明）（Now read the question. / You now have 90 seconds ... など）を除く。
本文を誤って消さないよう、決まった形に小片全体が当てはまる時と、説明に挟まれた短い切れ端だけを除く。
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


# 本文の中でも、ここから先は指示文と分かる言い回し（句点が無く本文とつながって文字起こしされた時に切り分ける）
_STRONG_RE = re.compile(r"(?:now,? )?read the questions?[.?!]?|(?:you|we) now have \S+ (?:seconds|minutes?) to [^.?!]*[.?!]?"
                        r"|(?:that )?is the end of (?:listening )?part [abc][.?!]?|now,? (?:turn over and )?look at (?:extract|part|question|the notes)\b[^.?!]*[.?!]?"
                        r"|complete your answers as you listen[.?!]?|extract \S+,? questions? \S+ (?:to|-) ?\S+[.?!]?", re.I)
# 場面の説明（You hear a nurse talking to ...）。前置き（Listening part B, / Question 26. など）が付くこともある
_SCENE_RE = re.compile(r"(?:(?:listening|listing),? )?(?:in )?(?:part [abc][.,]? )?(?:question " + N + r"[.,]? )?"
                       r"(?:extract " + N + r"[.,]? (?:questions? " + N + r" (?:to|-) " + N + r"[.,]? )?)?"
                       r"you(?:'re\b|(?:'ll| will)? (?:now )?(?:hear|are|be)\b)", re.I)
# 文の頭が "You hear a/an/two ..." なら場所に関係なく場面の説明（会話では "can you hear me?" のように頭に来ない）
_SCENE_SURE_RE = re.compile(r"(?:(?:listening|listing),? )?(?:in )?(?:part [abc][.,]? )?(?:question " + N + r"[.,]? )?"
                            r"you hear (?:a|an|two|three|the|part|members|some)\b", re.I)
_TITLE_RE = re.compile(r"(?:occupational english test|oet)\b[^.?!]*[.?!]?|(?:sample|practice) test(?: \S+)?[.?!]?|listening test[.?!]?"
                       r"|this test has three parts[.?!]?|i'm going to give you the instructions for this test[.?!]?", re.I)
SCENE_GAP = 2.5


def _full(rx, text):
    t = text.strip()
    pos = 0
    while pos < len(t):
        m = rx.match(t, pos)
        if not m or m.end() == pos:
            return False
        pos = m.end()
        while pos < len(t) and t[pos] in ' ,.':
            pos += 1
    return bool(t)


def _pieces(g):
    """1つの文（語の並び）を、句点と指示文の切れ目で小片に分ける"""
    text, starts = '', []
    for w in g:
        starts.append(len(text))
        text += w[2]
    cuts = {0, len(g)}
    for k, w in enumerate(g[:-1]):
        if _ends_sentence(w[2], 99):
            cuts.add(k + 1)
    for m in _STRONG_RE.finditer(text):
        for pos in (m.start(), m.end()):
            k = next((k for k, st in enumerate(starts) if st >= pos - 1), len(g))
            cuts.add(k)
    cuts = sorted(cuts)
    return [g[a:b] for a, b in zip(cuts, cuts[1:]) if b > a]


def _txt(ws):
    return re.sub(r'\s+', ' ', ''.join(w[2] for w in ws)).strip()


def drop_narration(groups):
    """試験のナレーション（タイトル・指示文・場面の説明）を除き、本文の語の並びだけを返す。"""
    items = []  # [語の並び, 元の文番号, 除くか]
    for gi, g in enumerate(groups):
        for pc in _pieces(g):
            t = _txt(pc)
            items.append([pc, gi, is_instruction(t) or _full(_TITLE_RE, t), len(items)])
    # トラックの頭が説明の途中から始まっている時の切れ端（小文字で始まる）
    if items and not items[0][2] and items[0][0][0][0] < 10.0 and re.match(r"[a-z]", _txt(items[0][0])):
        items[0][2] = True
    # 場面の説明：指示文か長めの無音のとなりにあるものだけ（会話の中の "you hear" は残す）
    changed = True
    while changed:
        changed = False
        for k, it in enumerate(items):
            if it[2] or not _SCENE_RE.match(_txt(it[0])):
                continue
            gb = it[0][0][0] - items[k - 1][0][-1][1] if k else 99
            ga = items[k + 1][0][0][0] - it[0][-1][1] if k + 1 < len(items) else 99
            nb = k and items[k - 1][2]
            na = k + 1 < len(items) and items[k + 1][2]
            if gb >= SCENE_GAP or ga >= SCENE_GAP or nb or na or _SCENE_SURE_RE.match(_txt(it[0])):
                it[2] = changed = True
    # 説明と説明に挟まれた短い切れ端（"You'll have time to" + [read the questions] + "before you hear each extract..."）
    for k in range(1, len(items) - 1):
        if not items[k][2] and items[k - 1][2] and items[k + 1][2] and len(items[k][0]) <= 15:
            items[k][2] = True
    # 説明のあと、黙読時間の直前に取り残された1〜2語（"My" "I'm"）は次の本文の頭にくっつける
    for k in range(1, len(items) - 1):
        a, b = items[k], items[k + 1]
        if not a[2] and items[k - 1][2] and len(a[0]) <= 2 and not b[2] and b[0][0][0] - a[0][-1][1] >= 3.0:
            b[0] = [[b[0][0][0], b[0][0][0], w[2]] for w in a[0]] + b[0]
            a[2] = True
    keep = [it for it in items if not it[2]]
    # 同じ文から来た小片は1文に戻す（間に除いた小片があれば戻さない）
    out = []
    for it in keep:
        if not it[0]:
            continue
        if out and out[-1][1] == it[1] and out[-1][2] == it[3] - 1:
            out[-1][0] = out[-1][0] + it[0]
            out[-1][2] = it[3]
        else:
            out.append([it[0], it[1], it[3]])
    return [o[0] for o in out]


def segment(words, dur=None, drop=False):
    """words: [[start, end, text], ...] → [[start, end, text], ...]。drop=True でナレーションを除く"""
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
    if drop:
        groups = drop_narration(groups)
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
