#!/usr/bin/env bash
# 全テストを走らせる（リポジトリのトップから）: bash tests/run_all.sh
# 元のテスト（tests/source/11・12）は、フォルダごとに別プロセスで走らせる。
# 2 つは同じ名前のモジュール（_common・test_common.py など）を使うため、一緒に走らせると取り違える。
# 環境変数：PYTHON_VERSION（既定 3.12）
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON_VERSION:-3.12}"
status=0
for target in tests/source/11 tests/source/12 "tests --ignore=tests/source"; do
  echo "== pytest $target"
  # shellcheck disable=SC2086
  uv run --python "$PY" pytest -q -p no:cacheprovider $target || status=1
done
[ "$status" -eq 0 ] && echo "PASS: 全テストが通る" || echo "FAIL: 失敗がある"
exit "$status"
