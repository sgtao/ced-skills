#!/usr/bin/env bash
# 合格条件 3：一時の CLAUDE_CONFIG_DIR でプラグインだけを入れると、スキル 4 つとコマンド explain の計 5 つが認識される
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export CLAUDE_CONFIG_DIR="$TMP/config"
mkdir -p "$CLAUDE_CONFIG_DIR"
cd "$TMP" || exit 1

claude plugin marketplace add "$ROOT" || { echo "FAIL: marketplace add"; exit 1; }
claude plugin install ced-skills@ced-skills || { echo "FAIL: install"; exit 1; }
details="$(claude plugin details ced-skills@ced-skills 2>&1)"
echo "$details"

inv=$(echo "$details" | grep -E '^ *Skills \(' | head -1)
total=$(echo "$inv" | grep -oE 'Skills \([0-9]+\)' | grep -oE '[0-9]+')
names=$(echo "$inv" | grep -oE 'ced-(url-to-md|pdf-to-md-ja|craft-explanation-docs|websearch-slide-ja)|explain' | sort -u | wc -l | tr -d ' ')
echo "components listed: ${total:-none} (want 5); matched names: $names (want 5: 4 ced- skills + explain)"
fail=0
[ "${total:-0}" -eq 5 ] && [ "$names" -eq 5 ] || { echo "FAIL: component inventory"; fail=1; }
claude plugin uninstall ced-skills@ced-skills >/dev/null 2>&1
claude plugin marketplace remove ced-skills >/dev/null 2>&1
[ "$fail" -eq 0 ] && echo "PASS: plugin install (5 components)" || echo "FAIL: plugin install"
exit "$fail"
