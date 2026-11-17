# E2E 記録：M1・HTML 1 件（2026-11-17）

- 入力：`tests/fixtures/e2e/input.html`（自作の固定の記事）
- 起動：`claude -p "/ced-skills:explain <入力> --out <出力> --slides 6 --audience Claude Code を始めたばかりの人" --plugin-dir plugins/ced-skills --output-format stream-json --verbose --max-budget-usd 8 --allowedTools "Skill Bash Read Write Edit Glob Grep WebSearch WebFetch"`
- 設定：`CLAUDE_CONFIG_DIR` の一時設定はログインできなかったため（Not logged in）使わず、`--plugin-dir` で読み込んだ。ユーザーの既存スキルも同時に読まれている可能性がある。読まれたスキルは stream-json の Skill 呼び出しで確かめた（`ced-skills:ced-url-to-md`・`ced-craft-explanation-docs`・`ced-websearch-slide-ja`）
- 結果：success、50 ターン、272 秒、約 $2.07。AskUserQuestion の呼び出し 0 回、権限の拒否 0 回
- 検査：`tests/e2e_check.py` の結果は `check.json`（7・8 すべて PASS、lint error 0・warn 0）
- 気づいたこと：スライド MD の確認を経ずに HTML を作った（質問を出さない実行のため）。また入力の記事にない「/plugin」の説明を、補足として解説メモとスライドに入れた（本人が補足と明記）。どちらも M3（explain の扱い）と、M5 の審査で見る
