#!/usr/bin/env bash
# =============================================================================
# install.sh — ced-skills の 4 スキルを、プラグインを使わずに skills フォルダへ入れる・外す
#
# 対象は Claude Code だけ（--target claude）。入れるのは ced- の 4 スキルだけで、
# 同じ名前のフォルダは入れ直し、ほかのスキル（元の名前の url-to-md などを含む）には触らない。
#
# Usage:
#   bash scripts/install.sh --scope user               # ~/.claude/skills へ
#   bash scripts/install.sh --scope project --project-dir ~/work/app   # <dir>/.claude/skills へ
#   bash scripts/install.sh --dir /path/to/skills      # 任意の配置先へ
#   bash scripts/install.sh --scope user --uninstall   # 同じ指定の配置先から、ced- の 4 つだけ消す
#   bash scripts/install.sh --scope user --dry-run     # 何も書かず、行う操作だけ表示する
#   bash scripts/install.sh --list-targets
#
# 確認は、対象の一覧を出してから 1 回だけ聞く。-y / --yes で聞かずに実行する。
# 環境変数 CLAUDE_SKILLS_DIR を設定すると、--scope user の配置先を上書きする。
# =============================================================================
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${REPO}/plugins"
SKILLS="ced-url-to-md ced-pdf-to-md-ja ced-craft-explanation-docs ced-websearch-slide-ja"

TARGET="claude"
SCOPE="user"
PROJECT_DIR=""
DEST_OVERRIDE=""
MODE="install"   # install | uninstall
DRY_RUN=0
ASSUME_YES=0

usage() {
  sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
}

die() { echo "[ERROR] $*" >&2; exit 1; }

list_targets() {
  cat <<'EOT'
ツール     スコープ   配置先
claude     user       ${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}
claude     project    <--project-dir>/.claude/skills（既定はカレントディレクトリ）
（--dir <path> で任意の配置先を直接指定できる）
EOT
}

while [ $# -gt 0 ]; do
  case "$1" in
    -t|--target)     TARGET="${2:-}"; shift 2 ;;
    --scope)         SCOPE="${2:-}"; shift 2 ;;
    --project-dir)   PROJECT_DIR="${2:-}"; shift 2 ;;
    --dir)           DEST_OVERRIDE="${2:-}"; shift 2 ;;
    --uninstall)     MODE="uninstall"; shift ;;
    --dry-run)       DRY_RUN=1; shift ;;
    --list-targets)  list_targets; exit 0 ;;
    -y|--yes)        ASSUME_YES=1; shift ;;
    -h|--help)       usage; exit 0 ;;
    *) die "不明なオプション: $1（--help を見る）" ;;
  esac
done

[ "$TARGET" = "claude" ] || die "未対応のツール: ${TARGET}（今は claude だけ対応）"

# 配置先を決める
if [ -n "$DEST_OVERRIDE" ]; then
  DEST="$DEST_OVERRIDE"
else
  case "$SCOPE" in
    user)
      DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}" ;;
    project)
      base="${PROJECT_DIR:-$PWD}"
      [ -d "$base" ] || die "--project-dir が見つからない: ${base}"
      DEST="${base%/}/.claude/skills" ;;
    *) die "不明なスコープ: ${SCOPE}（user か project）" ;;
  esac
fi

# 対象の一覧を出す
echo "モード: ${MODE}$( [ "$DRY_RUN" -eq 1 ] && echo '（dry-run）')"
echo "配置先: ${DEST}"
for s in $SKILLS; do
  if [ "$MODE" = "install" ]; then
    echo "  入れる: ${s}"
  else
    echo "  消す:   ${s}（あれば）"
  fi
done

# 確認（dry-run と -y のときは聞かない）
if [ "$DRY_RUN" -eq 0 ] && [ "$ASSUME_YES" -eq 0 ]; then
  printf "実行しますか？ [y/N] "
  read -r answer || answer=""
  case "$answer" in
    y|Y) ;;
    *) echo "中止しました。"; exit 0 ;;
  esac
fi

run() {
  # 1 つの操作を実行する。dry-run のときは表示だけ
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[DRY-RUN] $*"
  else
    "$@"
  fi
}

if [ "$MODE" = "install" ]; then
  for s in $SKILLS; do
    [ -f "${SRC}/${s}/SKILL.md" ] || die "複製元が見つからない: ${SRC}/${s}（sync_skills.py を先に実行）"
  done
  run mkdir -p "$DEST"
  for s in $SKILLS; do
    run rm -rf "${DEST}/${s}"
    run cp -R "${SRC}/${s}" "${DEST}/${s}"
    [ "$DRY_RUN" -eq 1 ] || echo "[OK] 入れました: ${s}"
  done
else
  for s in $SKILLS; do
    if [ -e "${DEST}/${s}" ]; then
      run rm -rf "${DEST}/${s}"
      [ "$DRY_RUN" -eq 1 ] || echo "[OK] 消しました: ${s}"
    fi
  done
fi

[ "$DRY_RUN" -eq 1 ] && echo "dry-run のため、何も変えていません。"
exit 0
