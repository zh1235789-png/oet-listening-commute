#!/bin/zsh
# 圧縮＋文字起こしを最後まで回し、そろったら暗号化して公開する（アプリを閉じても続くよう nohup で起動する）
#   nohup build/finish.sh > ~/.cache/oet-listening-commute/finish.log 2>&1 &
# 途中で止まっても、もう一度起動すれば未処理分から続きをやる。
set -u
cd "${0:A:h}/.."
LOG=~/.cache/oet-listening-commute/prepare.log
caffeinate -i ~/whisper-env/bin/python build/prepare.py 2>&1 | grep --line-buffered -v -E "mel_spec|RuntimeWarning|warn" >> "$LOG"
echo "== $(date '+%F %T') prepare 終了"
python3 build/build.py || { echo "build 失敗"; exit 1; }
node --test "tests/*.test.mjs" 2>&1 | grep -E "^ℹ (pass|fail)|^✖" ; [ ${pipestatus[1]} -eq 0 ] || { echo "テスト失敗。push しない"; exit 1; }
git add -A && git commit -q -m "全模試の音源とスクリプトを追加（自動）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git push 2>&1 | tail -5
echo "== $(date '+%F %T') 完了"
