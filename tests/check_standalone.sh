#!/usr/bin/env bash
# 合格条件 1（単独開発）：01_sources の無い一時フォルダに ced-skills だけをクローンし、
# 全テストが通ることと、元のリポジトリへの参照が残っていないことを確かめる。
#
# 使い方（リポジトリのトップから）: bash tests/check_standalone.sh [--worktree]
# --worktree：コミット前に、作業ツリー（追跡中と未追跡の、ignore 以外）をコピーして確かめる
# 注意：クローンは commit 済みの内容（HEAD）を使う。未コミットの変更は入らないので、警告を出す。
# 環境変数：PYTHON_VERSION（既定 3.12。onnxruntime が 3.14 の wheel を持たないため）、KEEP=1 で作業フォルダを残す
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON_VERSION:-3.12}"
WORK="$(mktemp -d)"
CLONE="$WORK/ced-skills"
status=0

fail() { echo "FAIL: $1"; status=1; }

if [ "${1:-}" != "--worktree" ] && [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
  echo "警告: 作業ツリーに未コミットの変更がある。クローンには入らない（HEAD で確かめる）"
fi

if [ "${1:-}" = "--worktree" ]; then
  # コミット前に確かめる用：追跡中と未追跡（ignore 以外）のファイルを、クローンの代わりにコピーする
  mkdir -p "$CLONE"
  (cd "$ROOT" && git ls-files -co --exclude-standard -z | tar --null -T - -cf -) | (cd "$CLONE" && tar xf -) || { echo "FAIL: コピーできない"; exit 2; }
else
  git clone -q "$ROOT" "$CLONE" || { echo "FAIL: クローンできない"; exit 2; }
fi

# 1. 01_sources が無い場所であること（元のリポジトリに頼らないこと）
[ -e "$CLONE/01_sources" ] && fail "クローンに 01_sources がある"
[ -e "$CLONE/pyproject.toml" ] && [ -e "$CLONE/uv.lock" ] || fail "pyproject.toml または uv.lock が無い"

# 2. 同期の仕組みと元のリポジトリへの参照が残っていないこと（履歴の CHANGELOG は除く）
banned='sync_skills|sources\.lock|run_source_tests|source-exclusions|11_dev-skill|12_dev-skill|13_dev-skill|skill-web-to-markdown-ja|skill-craft-explanation-docs|skill-websearch-slide-ja'
hits=$(cd "$CLONE" && grep -InE "$banned|01_sources" README.md docs; grep -rInE "$banned" scripts plugins adapters tests \
        --exclude=check_standalone.sh --exclude-dir=__pycache__ --exclude-dir=.git 2>/dev/null)
if [ -n "$hits" ]; then
  echo "$hits"
  fail "元のリポジトリ・同期の仕組みへの参照が残っている（上の行）"
fi
for f in sync_skills.py sources.lock.json run_source_tests.sh source-exclusions.txt; do
  found=$(cd "$CLONE" && find . -name "$f" -not -path './.git/*')
  [ -n "$found" ] && fail "消すべきファイルが残っている: $found"
done

# 3. 全テストが通ること（移した元のテスト tests/source/ と既存の検査）
if [ "$status" -eq 0 ]; then
  (cd "$CLONE" && PYTHON_VERSION="$PY" bash tests/run_all.sh)
  rc=$?
  [ "$rc" -eq 0 ] || fail "テストに失敗がある（run_all.sh の終了コード $rc）"
fi

if [ "${KEEP:-0}" = "1" ]; then echo "作業フォルダ: $WORK"; else rm -rf "$WORK"; fi
if [ "$status" -eq 0 ]; then echo "PASS: 01_sources の無いクローンで、参照の残りが無く全テストが通る"; fi
exit "$status"
