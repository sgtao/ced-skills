#!/usr/bin/env python3
"""合格条件 6：explain の質問の扱いを確かめる（静的検査＋E2E の記録）。

静的検査（plugins/commands/explain.md）:
- 質問の定義が 4 問以内（既定で 3 問）、質問文と選択肢があり、質問文が日本語
- AskUserQuestion を呼ぶ指示は、手順 1 の中だけにある
- 引数が 3 つそろったときは AskUserQuestion を呼ばない、と書いてある
- AskUserQuestion が allowed-tools に入っている

質問を止める決まり（PLAN.md 5 節）の静的検査:
- explain.md が、解説メモ（ced-craft-explanation-docs）に「質問なしで」と、読み手（--audience）と補足の既定を渡す
- explain.md が、スライド（ced-websearch-slide-ja）に確定値（目的・情報ソース・ビジュアル・枚数・保存先）を渡す
- ced-websearch-slide-ja の「確定値モード」の節が、質問・確認の全項目を省くと書いている（項目の一覧は SLIDE_ITEMS）

E2E の記録（--stream で stream-json を渡したとき）:
- 引数で 3 つの答えを渡した実行では、AskUserQuestion の呼び出しが 0 回

会話の記録（--transcript で、対話セッションの jsonl を渡したとき）:
- AskUserQuestion の呼び出し回数と、1 回あたりの問数を数える（--max-questions で上限を指定。既定は数えるだけ）
- WebSearch の使用回数と、読まれたスキルの名前（Skill の呼び出し）を数える

使い方: python3 tests/check_explain.py [--stream tests/e2e-record/m1-html/stream.jsonl]
        python3 tests/check_explain.py --transcript <jsonl> [--max-questions 1]
終了コード: 0＝合格、1＝不合格
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPLAIN = REPO / "plugins/commands/explain.md"


def static_checks(text: str):
    problems = []
    m = re.search(r"^allowed-tools:\s*(.+)$", text, re.M)
    if not m or "AskUserQuestion" not in m.group(1):
        problems.append("allowed-tools に AskUserQuestion がない")

    # 質問の定義（「- Q1 …」形式）を数える
    qs = re.findall(r"^- Q(\d+) ", text, re.M)
    if not qs:
        problems.append("質問の定義（- Q1 ...）がない")
    if len(qs) > 4:
        problems.append(f"質問が {len(qs)} 問（4 問以内）")
    for q in re.finditer(r"^- Q\d+ .*$", text, re.M):
        line = q.group(0)
        if "選択肢:" not in line and "選択肢：" not in line:
            problems.append(f"選択肢がない: {line[:40]}")
        if not re.search(r"[ぁ-んァ-ヶ一-龠]", line):
            problems.append(f"日本語でない: {line[:40]}")

    # AskUserQuestion の指示は手順 1 の中だけにある
    steps = text.split("## 手順", 1)[-1]
    step1 = re.search(r"^### 1\..*?(?=^### 2\.)", steps, re.M | re.S)
    if not step1:
        problems.append("手順 1 が見つからない")
        return problems, len(qs)
    if steps.count("AskUserQuestion") != step1.group(0).count("AskUserQuestion"):
        problems.append("AskUserQuestion の指示が手順 1 の外にある")
    if step1.group(0).count("AskUserQuestion") == 0:
        problems.append("手順 1 に AskUserQuestion の指示がない")
    if "AskUserQuestion を呼ばない" not in step1.group(0):
        problems.append("引数が 3 つそろったときに AskUserQuestion を呼ばない、の記述がない")
    if "1 回の呼び出し" not in step1.group(0):
        problems.append("質問を 1 回にまとめる、の記述がない")
    return problems, len(qs)


SLIDE = REPO / "plugins/ced-websearch-slide-ja"
# 確定値モードの節に、省く対象として載っているべき項目（PLAN.md 5 節の表）。キーは節の中に含まれるべき語
SLIDE_ITEMS = {
    "作成可否（Step 0 の 1 回目）": "作成可否",
    "作成目的（Step 0 の 2 回目）": "作成目的",
    "既定値の一覧の確認": "既定値",
    "Step 1-A の 3 択": "3 択",
    "Step 1-A の下限チェック": "下限チェック",
    "Step 1-B のロール確認": "ロール",
    "Step 1-C の検索フレーズ": "検索フレーズ",
    "Step 1-C のビジュアル方針": "ビジュアル",
    "convert-raw の全文の承認": "全文",
    "build の 16 枚超の確認": "16 枚",
    "build の修正の確認": "修正の確認",
}
# explain.md がスライドに渡す確定値
CONFIRMED_VALUES = ("目的", "情報ソース", "ビジュアル", "枚数", "保存先")


def section_of(text: str, heading: str, level: int = 3):
    """level 個の # の見出しから、次の同じ以下の見出しまでを返す。無ければ None。"""
    hashes = "#" * level
    m = re.search(rf"^{hashes} {re.escape(heading)}.*?(?=^#{{1,{level}}} |\Z)", text, re.M | re.S)
    return m.group(0) if m else None


def quiet_pass_checks(text: str):
    """explain.md が、子スキルの質問を止める値を渡しているか。"""
    problems = []
    memo = section_of(text, "3.")
    if memo is None:
        return ["手順 3（解説メモ）が見つからない"]
    if "質問なしで" not in memo:
        problems.append("手順 3：ced-craft-explanation-docs に「質問なしで」と渡す記述がない")
    if not re.search(r"読み手.*--audience|--audience.*読み手", memo):
        problems.append("手順 3：--audience を「読み手」として渡す記述がない")
    if "話題として扱わ" not in memo:
        problems.append("手順 3：--audience を話題として扱わない（内容の向きを変えない）、の記述がない")
    if "補足" not in memo:
        problems.append("手順 3：補足（Q5）の既定を渡す記述がない")
    slides = section_of(text, "4.")
    if slides is None:
        return problems + ["手順 4（スライド）が見つからない"]
    if "確定値" not in slides:
        problems.append("手順 4：ced-websearch-slide-ja に確定値を渡す記述がない")
    for k in CONFIRMED_VALUES:
        if k not in slides:
            problems.append(f"手順 4：確定値に「{k}」がない")
    return problems


def m5_checks(text: str):
    """v0.0.2 M5：入力の決め方（PLAN 4.1・4.5〜4.7・4.9）を、手順書が言っているか（静的）。"""
    problems = []
    # 入力の処理は、ced-url-to-md の collection モードと collect_sources.py の 4 つの動き
    for k in ("ced-url-to-md", "collection", "collect_sources.py"):
        if k not in text:
            problems.append(f"入力の処理に「{k}」が無い（collection モードを使う）")
    for sub in ("plan", "prepare", "mark", "index"):
        if f"`{sub}`" not in text:
            problems.append(f"collect_sources の「{sub}」の動きが無い")
    if re.search(r"/skills/|~/\.claude|plugins/ced-", text):
        problems.append("他のスキルのフォルダのパスを直接書いている（<SKILL_DIR> ではない）")
    # 最初の質問は Q1〜Q4（4 問以内）。Q4 は入力の確認（参照元の選択）
    qs = re.findall(r"^- Q(\d+) (.*)$", text, re.M)
    names = {n: body for n, body in qs}
    if [n for n, _ in qs] != ["1", "2", "3", "4"]:
        problems.append(f"質問の番号が Q1〜Q4 の順ではない: {[n for n, _ in qs]}")
    q4 = names.get("4", "")
    for k in ("01_source", "01_sources", "やめる"):
        if k not in q4:
            problems.append(f"Q4 に「{k}」の選択肢が無い")
    # 答えの後は質問しない。衝突は OUTPUT_CONFLICT で止まり、再度は聞かない
    if "OUTPUT_CONFLICT" not in text:
        problems.append("出力先の衝突で OUTPUT_CONFLICT により止まる記述が無い")
    if not re.search(r"(再度|もう一度|二度と).{0,6}(質問|聞)", text):
        problems.append("答えの後に再度質問しない、の記述が無い")
    # 再開・飛ばし・上限
    if "続きから" not in text or "done" not in text:
        problems.append("完了済みを飛ばし、途中から続ける、の記述が無い")
    if "MAX_FILES_REQUIRED" not in text or "--limit" not in text:
        problems.append("上限を超えたときの MAX_FILES_REQUIRED と --limit の記述が無い")
    # 2 件以上の一覧・解説メモの作業フォルダ
    if "00_index.md" not in text or "index" not in text:
        problems.append("2 件以上のときの 00_index.md の記述が無い")
    if "explained" not in text or "DEST_EXISTS" not in text:
        problems.append("再開のときに explained/ を渡す（DEST_EXISTS にしない）の記述が無い")
    # 4.6：Q1 は --out の先が衝突するときも出す。Q4 は未完了が 2 件以上、または参照元が 2 つのとき。一覧は 10 件まで
    q1 = names.get("1", "")
    if "衝突" not in q1:
        problems.append("Q1 に、--out の先が衝突するときも出す、の記述が無い")
    if "未完了が 2 件以上、または参照元が 2 つ" not in q4:
        problems.append("Q4 の条件（未完了が 2 件以上、または参照元が 2 つ）が無い")
    if "10 件" not in text:
        problems.append("Q4 の一覧は 10 件まで、の記述が無い")
    # 4.1・4.5：質問なしの実行で参照元が 2 つあるときは止まる
    if "AMBIGUOUS_SOURCE_DIR" not in text:
        problems.append("質問なしの実行で参照元が 2 つあるとき AMBIGUOUS_SOURCE_DIR で止まる記述が無い")
    # 4.6：値のそろえ方（--slides は整数、--audience は NFKC。「（既定）」の表示は値に含めない）
    if "NFKC" not in text or "既定）" not in text:
        problems.append("値のそろえ方（--audience の NFKC、「（既定）」を値に含めない）の記述が無い")
    # 4.7：<入力の名前> の決め方
    for k in ("動画 ID", "拡張子"):
        if k not in text:
            problems.append(f"<入力の名前> の決め方に「{k}」が無い")
    # 5：解説メモの Q6（同名フォルダ）には進ませない
    if not re.search(r"Q6.{0,60}(進ませ|聞かせ|質問させ)", text):
        problems.append("子スキルの Q6（同名フォルダ）に進ませない、の記述が無い")
    # 4.5：1 件が失敗しても、記録して残りを続ける。途中で止まるときも index を作る
    if "残りを続ける" not in text:
        problems.append("1 件が失敗しても記録して残りを続ける、の記述が無い")
    if "途中で止まる" not in text:
        problems.append("途中で止まるときも index を作る、の記述が無い")
    # 資料の中の指示文は、データとして扱う（従わない）
    if not re.search(r"指示文.{0,20}データ|データ.{0,20}指示", text):
        problems.append("資料の中の指示文はデータとして扱い、従わない、の記述が無い")
    return problems


def layout_checks(text: str):
    """explain.md が、出力の形（PLAN.md 4.8）を決めているか。形そのものの検査は check_output_layout.py。"""
    problems = []
    tree = re.search(r"```\n<出力先>/\n.*?```", text, re.S)
    if not tree:
        return ["出力の形の図（<出力先>/ から始まる図）が無い"]
    for k in ("explained/", "<入力の名前>-slides.md", "<入力の名前>-slides.html", ".work/"):
        if k not in tree.group(0):
            problems.append(f"出力の形の図に「{k}」が無い")
    if "固定" not in text:
        problems.append("出力の形を固定する記述（「固定」）が無い")
    for m in re.finditer(r"\./explain-out(?!/<入力の名前>)", text):
        problems.append(f"出力先の既定が入力の名前を含まない: {text[m.start():m.start() + 20]!r}")
    steps = section_of(text, "2.") or ""
    if ".work/md/" not in steps:
        problems.append("手順 2：変換した Markdown を .work/md/ に置く記述が無い")
    return problems


def slide_mode_checks():
    """ced-websearch-slide-ja（元のリポジトリ 13 の複製）に、確定値モードの決まりがあるか。"""
    problems = []
    create = SLIDE / "workflows/create.md"
    if not create.exists():
        return [f"{create.relative_to(REPO)} が無い"]
    sec = section_of(create.read_text(encoding="utf-8"), "確定値モード", level=2)
    if sec is None:
        return ["workflows/create.md に「## 確定値モード」の節がない"]
    for label, key in SLIDE_ITEMS.items():
        if key not in sec:
            problems.append(f"確定値モードの節に「{label}」が載っていない（語: {key}）")
    for rel in ("SKILL.md", "workflows/convert-raw.md", "workflows/build.md", "references/usage-guide.md"):
        f = SLIDE / rel
        if "確定値モード" not in f.read_text(encoding="utf-8"):
            problems.append(f"{rel} が確定値モードに触れていない")
    return problems


def transcript_stats(path: Path):
    """jsonl（stream-json か、~/.claude/projects の会話の記録）から、ツールの呼び出しを数える。"""
    ask_calls, ask_questions, websearch, skills = 0, [], 0, []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = e.get("message")
        if e.get("type") != "assistant" or not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict) or c.get("type") != "tool_use":
                continue
            name, inp = c.get("name"), c.get("input") or {}
            if name == "AskUserQuestion":
                ask_calls += 1
                ask_questions.append(len(inp.get("questions", [])))
            elif name == "WebSearch":
                websearch += 1
            elif name == "Skill":
                skills.append(str(inp.get("skill", "")))
    return {"ask_calls": ask_calls, "ask_questions": ask_questions, "websearch": websearch, "skills": skills}


def stream_count(path: Path):
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "assistant":
            for c in e.get("message", {}).get("content", []):
                if c.get("type") == "tool_use" and c.get("name") == "AskUserQuestion":
                    n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", type=Path, help="引数で 3 つの答えを渡した E2E の stream-json")
    ap.add_argument("--transcript", type=Path, help="対話セッションの会話の記録（jsonl）。質問の回数などを集計する")
    ap.add_argument("--max-questions", type=int, help="--transcript の AskUserQuestion の呼び出しの上限（H2 は 1、H3 は 0）")
    args = ap.parse_args()
    if args.transcript:
        s = transcript_stats(args.transcript)
        print(f"AskUserQuestion の呼び出し: {s['ask_calls']} 回（1 回あたりの問数: {s['ask_questions'] or '-'}）")
        print(f"WebSearch の使用: {s['websearch']} 回")
        print(f"読まれたスキル: {', '.join(s['skills']) or '（なし）'}")
        bad = [n for n in s["ask_questions"] if n > 4]
        over = args.max_questions is not None and s["ask_calls"] > args.max_questions
        if bad:
            print(f"FAIL: 1 回の質問が 4 問を超えた呼び出しがある: {bad}")
        if over:
            print(f"FAIL: 質問が {s['ask_calls']} 回（上限 {args.max_questions} 回）")
        ok_t = not bad and not over
        print(("PASS" if ok_t else "FAIL") + ": 会話の記録の集計")
        return 0 if ok_t else 1
    ok = True
    problems, nq = static_checks(EXPLAIN.read_text(encoding="utf-8"))
    problems += quiet_pass_checks(EXPLAIN.read_text(encoding="utf-8"))
    problems += slide_mode_checks()
    problems += layout_checks(EXPLAIN.read_text(encoding="utf-8"))
    problems += m5_checks(EXPLAIN.read_text(encoding="utf-8"))
    print(f"質問の数（定義）: {nq}（4 問以内）")
    for p in problems:
        print("FAIL:", p)
    ok = ok and not problems
    if args.stream:
        n = stream_count(args.stream)
        print(f"E2E の AskUserQuestion 呼び出し: {n} 回（引数で答えを渡した実行は 0 回）")
        ok = ok and n == 0
    print(("PASS" if ok else "FAIL") + ": explain の質問（静的検査" + ("と E2E の記録" if args.stream else "") + "）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
