#!/usr/bin/env bash
# 合格条件 5：元のリポジトリ（11 と 12）の pytest を、複製したスキルに向けて実行し、失敗 0 を確かめる。
#
# 作業フォルダ（一時）に、元のテストの配置を再現する。スキルのフォルダだけは
# 複製（plugins/ced-*）へのシンボリックリンクで、元の名前（url-to-md など）にする。
# テストは元のままで、外すものは tests/source-exclusions.txt に理由付きで書く。
#
# 使い方（リポジトリのトップから）: bash tests/run_source_tests.sh
# 環境変数: PYTHON_VERSION（既定 3.12。onnxruntime が 3.14 の wheel を持たないため）、KEEP=1 で作業フォルダを残す
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${ROOT}/plugins"
ORIG="${CED_SOURCES:-${ROOT}/../../01_sources}"   # 元のリポジトリの 01_sources（既定の場所）
PY="${PYTHON_VERSION:-3.12}"
EXCL="${ROOT}/tests/source-exclusions.txt"

[ -d "$ORIG/11_dev-skill-web-to-markdown-ja" ] || { echo "元のリポジトリが見つからない: $ORIG"; exit 2; }
WS="$(mktemp -d)/ws"
mkdir -p "$WS/11_dev-skill-web-to-markdown-ja" "$WS/12_dev-skill-craft-explanation-docs"

# 元のテストと依存の定義をコピー（.venv・キャッシュは含めない）
for s in 11_dev-skill-web-to-markdown-ja 12_dev-skill-craft-explanation-docs; do
  cp -R "$ORIG/$s/tests" "$WS/$s/"
  cp "$ORIG/$s/pyproject.toml" "$ORIG/$s/uv.lock" "$WS/$s/"
  find "$WS/$s" -name __pycache__ -prune -exec rm -rf {} +
done
# スキルのフォルダを複製へ向ける（元の名前で見える）
ln -s "$SRC/ced-url-to-md"               "$WS/11_dev-skill-web-to-markdown-ja/url-to-md"
ln -s "$SRC/ced-pdf-to-md-ja"            "$WS/11_dev-skill-web-to-markdown-ja/pdf-to-md-ja"
ln -s "$SRC/ced-craft-explanation-docs"  "$WS/12_dev-skill-craft-explanation-docs/craft-explanation-docs"

# 外すものを読む
IGNORE=(); DESELECT=()
while IFS='|' read -r suite target reason; do
  case "$suite" in ''|\#*) continue ;; esac
  if [[ "$target" == *"::"* ]]; then DESELECT+=("--deselect" "$target"); else IGNORE+=("--ignore=$target"); fi
  echo "外す [$suite] $target"
done < "$EXCL"

status=0
for s in 11_dev-skill-web-to-markdown-ja 12_dev-skill-craft-explanation-docs; do
  echo "== $s"
  ex=()
  while IFS='|' read -r suite target reason; do
    case "$suite" in ''|\#*) continue ;; esac
    [ "${s:0:2}" = "$suite" ] || continue
    if [[ "$target" == *"::"* ]]; then ex+=("--deselect" "$target"); else ex+=("--ignore=$target"); fi
  done < "$EXCL"
  (cd "$WS/$s" && uv run --python "$PY" --with pytest pytest -q -p no:cacheprovider "${ex[@]}")
  rc=$?
  [ "$rc" -eq 0 ] || status=1
done

if [ "${KEEP:-0}" = "1" ]; then echo "作業フォルダ: $WS"; else rm -rf "$(dirname "$WS")"; fi
[ "$status" -eq 0 ] && echo "PASS: 元のテスト（11・12）を複製に向けて実行し、失敗 0" || echo "FAIL: 元のテストに失敗がある"
exit "$status"
