#!/usr/bin/env bash
# =============================================================================
# install.sh — ced-skills の 4 スキルを、プラグインを使わずに各ツールのスキルのフォルダへ入れる・外す
#
# 対象のツール（--target）と、配置先（PLAN 6 節の表）:
#   claude       ~/.claude/skills          / <dir>/.claude/skills
#   agents       ~/.agents/skills          / <dir>/.agents/skills     （別名 codex・gemini）
#   copilot      ~/.copilot/skills         / <dir>/.github/skills
#   antigravity  ~/.gemini/config/skills   / <dir>/.agents/skills
#   all          claude・agents・antigravity の各配置先（同じ場所には 1 回だけ入れる）
#
# 入れるのは ced- の 4 スキルだけ。同じ名前のフォルダは入れ直し、ほかのスキル（元の名前の
# url-to-md などを含む）には触らない。
#
# Usage:
#   bash scripts/install.sh --scope user                          # 既定は --target claude
#   bash scripts/install.sh --target all --scope project --project-dir ~/work/app
#   bash scripts/install.sh --target copilot --scope user
#   bash scripts/install.sh --dir /path/to/skills                 # 任意の配置先へ（単一の --target と使う。all とは使えない）
#   bash scripts/install.sh --scope user --uninstall              # 同じ指定の配置先から、ced- の 4 つだけ消す
#   bash scripts/install.sh --scope user --dry-run                # 何も書かず、行う操作だけ表示する
#   bash scripts/install.sh --list-targets
#
# 確認は、対象の一覧を出してから 1 回だけ聞く。-y / --yes で聞かずに実行する。
# 環境変数 CLAUDE_SKILLS_DIR を設定すると、claude の --scope user の配置先を上書きする。
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
  # 先頭のコメント（set -euo の手前まで）を、罫線と shebang を除いて出す
  sed -n '1,/^set -euo/p' "$0" | grep -v '^#!' | grep -v '^set -euo' | grep -v '^# ====' | sed 's/^# \{0,1\}//'
}

die() { echo "[ERROR] $*" >&2; exit 1; }

# オプションの値があるか（--scope だけ、のように値を省くと、黙って止まらずに伝える）
need_value() {
  [ -n "${2:-}" ] || die "$1 には値が必要です（--help を見る）"
}

list_targets() {
  cat <<'EOT'
ツール        スコープ   配置先
claude        user       ${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}
claude        project    <--project-dir>/.claude/skills（既定はカレントディレクトリ）
agents        user       ~/.agents/skills        （別名: codex・gemini）
agents        project    <--project-dir>/.agents/skills
copilot       user       ~/.copilot/skills
copilot       project    <--project-dir>/.github/skills
antigravity   user       ~/.gemini/config/skills
antigravity   project    <--project-dir>/.agents/skills
all           （claude・agents・antigravity の配置先を、同じ場所は 1 回だけ）
（--dir <path> で任意の配置先を直接指定できる。単一の --target と組み合わせる。all とは組み合わせられない）
EOT
}

# 1 つのツールと、1 つのスコープの配置先を、改行で区切って返す
dests_for() {
  local tool="$1" scope="$2" base
  case "$scope" in
    user)
      case "$tool" in
        claude)      printf '%s\n' "${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}" ;;
        agents)      printf '%s\n' "$HOME/.agents/skills" ;;
        copilot)     printf '%s\n' "$HOME/.copilot/skills" ;;
        antigravity) printf '%s\n' "$HOME/.gemini/config/skills" ;;
      esac ;;
    project)
      base="${PROJECT_DIR:-$PWD}"
      [ -d "$base" ] || die "--project-dir が見つからない: ${base}"
      base="${base%/}"
      case "$tool" in
        claude)      printf '%s\n' "${base}/.claude/skills" ;;
        agents)      printf '%s\n' "${base}/.agents/skills" ;;
        copilot)     printf '%s\n' "${base}/.github/skills" ;;
        antigravity) printf '%s\n' "${base}/.agents/skills" ;;
      esac ;;
  esac
}

# 指定のツール（all は 3 つ）の配置先を、重ならないように並べる
resolve_dests() {
  local tools d out="" t
  case "$TARGET" in
    all) tools="claude agents antigravity" ;;
    *)   tools="$TARGET" ;;
  esac
  for t in $tools; do
    while IFS= read -r d; do
      [ -n "$d" ] || continue
      case "
${out}
" in
        *"	${d}
"*) ;;             # 同じ場所は 1 回だけ（最初のツールで入れる）
        *) out="${out}${t}	${d}
" ;;
      esac
    done <<EOT
$(dests_for "$t" "$SCOPE")
EOT
  done
  printf '%s' "$out"
}

while [ $# -gt 0 ]; do
  case "$1" in
    -t|--target)     need_value "$1" "${2:-}"; TARGET="$2"; shift 2 ;;
    --scope)         need_value "$1" "${2:-}"; SCOPE="$2"; shift 2 ;;
    --project-dir)   need_value "$1" "${2:-}"; PROJECT_DIR="$2"; shift 2 ;;
    --dir)           need_value "$1" "${2:-}"; DEST_OVERRIDE="$2"; shift 2 ;;
    --uninstall)     MODE="uninstall"; shift ;;
    --dry-run)       DRY_RUN=1; shift ;;
    --list-targets)  list_targets; exit 0 ;;
    -y|--yes)        ASSUME_YES=1; shift ;;
    -h|--help)       usage; exit 0 ;;
    *) die "不明なオプション: $1（--help を見る）" ;;
  esac
done

# 別名を正規の名前にそろえる
case "$TARGET" in
  codex|gemini) TARGET="agents" ;;
esac
case "$TARGET" in
  claude|agents|copilot|antigravity|all) ;;
  *) die "未対応のツール: ${TARGET}（claude・agents（codex・gemini）・copilot・antigravity・all のどれか）" ;;
esac
case "$SCOPE" in
  user|project) ;;
  *) die "不明なスコープ: ${SCOPE}（user か project）" ;;
esac

# --dir は単一のツールとだけ組み合わせられる（all とは、配置先が複数になるので組み合わせない）
if [ -n "$DEST_OVERRIDE" ] && [ "$TARGET" = "all" ]; then
  die "--dir は --target all と組み合わせられない（配置先を 1 か所に決めて、単一の --target と使う）"
fi

# 配置先を決める（--dir があれば 1 か所だけ）
if [ -n "$DEST_OVERRIDE" ]; then
  DESTS="${TARGET}	${DEST_OVERRIDE}
"
else
  DESTS="$(resolve_dests)"
fi
# 配置先だけの一覧（1 行 1 つ。ツールは DESTS の先頭の列）
DEST_LIST="$(printf '%s' "$DESTS" | cut -f2)"

in_dests() {
  case "
${DEST_LIST}
" in
    *"
$1
"*) return 0 ;;
  esac
  return 1
}

# ツールごとのスキル。ced-explain は Claude Code 以外に入れる（claude は、プラグインで入るので入れない）
skills_for() {
  if [ "$1" = "claude" ]; then echo "$SKILLS"; else echo "$SKILLS ced-explain"; fi
}

# スキルの複製元。ced-explain は adapters/ の生成物、ほかは plugins/ の複製
source_of() {
  if [ "$1" = "ced-explain" ]; then echo "${REPO}/adapters/ced-explain"; else echo "${SRC}/$1"; fi
}

has_ced() {
  local s
  for s in $SKILLS; do
    [ -e "$1/$s" ] && return 0
  done
  return 1
}

# Copilot CLI は .claude/skills と .agents/skills の両方を読む。プロジェクトで両方に ced- が入ると
# 同じスキルが二重に見えるので、入れる前に警告する（入れる操作の対象にした場合と、すでにある場合）
warn_overlap() {
  [ "$MODE" = "install" ] && [ "$SCOPE" = "project" ] && [ -z "$DEST_OVERRIDE" ] || return 0
  local base c a c_on=0 a_on=0
  base="${PROJECT_DIR:-$PWD}"; base="${base%/}"
  c="${base}/.claude/skills"; a="${base}/.agents/skills"
  if in_dests "$c" || has_ced "$c"; then c_on=1; fi
  if in_dests "$a" || has_ced "$a"; then a_on=1; fi
  if [ "$c_on" -eq 1 ] && [ "$a_on" -eq 1 ]; then
    echo "[WARN] ${c} と ${a} の両方に ced- のスキルが入ります。Copilot CLI は両方を読むので、同じスキルが二重に見えることがあります。どちらか一方にしてください。" >&2
  fi
}
warn_overlap

# 対象の一覧を出す
echo "モード: ${MODE}$( [ "$DRY_RUN" -eq 1 ] && echo '（dry-run）')"
while IFS= read -r d; do
  [ -n "$d" ] || continue
  echo "配置先: ${d}"
done <<EOT
${DEST_LIST}
EOT
for s in $(printf '%s\n' "$DESTS" | while IFS="	" read -r t _; do skills_for "$t"; done | tr ' ' '\n' | awk '!seen[$0]++'); do
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
  # ced-explain は claude 以外にだけ入るので、そのツールがある配置先のときだけ確かめる
  if printf '%s' "$DESTS" | cut -f1 | grep -qv '^claude$' && [ ! -f "${REPO}/adapters/ced-explain/SKILL.md" ]; then
    die "ced-explain が無い: adapters/ced-explain（python3 scripts/build_explain_skill.py で作る）"
  fi
fi

while IFS="	" read -r TOOL DEST; do
  [ -n "$DEST" ] || continue
  if [ "$MODE" = "install" ]; then
    run mkdir -p "$DEST"
    for s in $(skills_for "$TOOL"); do
      run rm -rf "${DEST}/${s}"
      run cp -R "$(source_of "$s")" "${DEST}/${s}"
      [ "$DRY_RUN" -eq 1 ] || echo "[OK] 入れました: ${s} → ${DEST}"
    done
  else
    for s in $(skills_for "$TOOL"); do
      if [ -e "${DEST}/${s}" ]; then
        run rm -rf "${DEST}/${s}"
        [ "$DRY_RUN" -eq 1 ] || echo "[OK] 消しました: ${s} ← ${DEST}"
      fi
    done
  fi
done <<EOT
${DESTS}
EOT

[ "$DRY_RUN" -eq 1 ] && echo "dry-run のため、何も変えていません。"
exit 0
