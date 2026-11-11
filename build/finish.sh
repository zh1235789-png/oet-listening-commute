#!/bin/zsh
# 圧縮＋文字起こしを最後まで回し、そろったら暗号化して公開する（アプリを閉じても続くよう nohup で起動する）
#   nohup build/finish.sh > ~/.cache/oet-listening-commute/finish.log 2>&1 &
# 途中で止まっても、もう一度起動すれば未処理分から続きをやる。
# 失敗したら「失敗」と書いて止まる（push まで行ったときだけ「完了」と書く）。
set -u
set -o pipefail
cd "${0:A:h}/.."
LOG=~/.cache/oet-listening-commute/prepare.log
fail() { echo "== $(date '+%F %T') 失敗: $1"; exit 1; }

caffeinate -i ~/whisper-env/bin/python build/prepare.py 2>&1 | grep --line-buffered -v -E "mel_spec|RuntimeWarning|warn" >> "$LOG"
[ ${pipestatus[1]} -eq 0 ] || fail "prepare.py（文字起こし）"
echo "== $(date '+%F %T') prepare 終了"

python3 build/translate.py || fail "translate.py（和訳）"

python3 build/build.py || fail "build.py"
node --test "tests/*.test.mjs" > /tmp/oet-lc-test.log 2>&1 || { grep -E "^✖|^ℹ (pass|fail)" /tmp/oet-lc-test.log; fail "テスト（push しない）"; }
grep -E "^ℹ (pass|fail)" /tmp/oet-lc-test.log

git add -A || fail "git add"
git commit -q -m "全模試の音源とスクリプトを追加（自動）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || fail "git commit"
git push 2>&1 | tail -8
[ ${pipestatus[1]} -eq 0 ] || fail "git push（pre-push で止まった可能性。上のログを見る）"
echo "== $(date '+%F %T') 完了"
