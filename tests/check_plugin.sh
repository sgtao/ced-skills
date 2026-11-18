#!/usr/bin/env bash
# 合格条件 1：claude plugin validate が、marketplace（リポジトリ直下）とプラグイン（plugins）の両方で exit 0・警告 0
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
fail=0
for target in "." "plugins"; do
  out="$(claude plugin validate "$target" 2>&1)"
  code=$?
  echo "== validate $target (exit $code)"
  echo "$out"
  if [ "$code" -ne 0 ]; then
    echo "FAIL: exit $code for $target"; fail=1
  fi
  if echo "$out" | grep -qiE 'warn'; then
    echo "FAIL: warnings for $target"; fail=1
  fi
done
[ "$fail" -eq 0 ] && echo "PASS: plugin validate (marketplace + plugin)" || echo "FAIL: plugin validate"
exit "$fail"
