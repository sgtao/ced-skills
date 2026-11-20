---
name: ced-craft-explanation-docs
description: |
  ced-url-to-md が作った Markdown（YouTube の字幕・Web 記事・PDF／Office 資料）を 1 つ渡すと、
  入力の種類によらず同じ形の解説メモ一式（README・本文の複製・解説メモ・FAQ・LLM 用プロンプト）を作る。
  「解説メモを作って」「この MD を解説して」「この資料を深掘りして」「講義メモにして」
  「この記事／動画／PDF を理解したい」「FAQ とガイド用プロンプトも作って」などで起動。
  「このスキルの使い方を教えて」「どう頼めばいい？」と聞かれたときは、何も作らず使い方を答える。
  対象外: Markdown への変換だけ（ced-url-to-md）、スライドだけ（ced-websearch-slide-ja）、
  GLOBIS 学び放題の講座フォルダの深掘り（globis-course-deepdive）。
---
# ced-craft-explanation-docs — 解説メモ一式を作るスキル

`ced-url-to-md` の出力 Markdown を **1 つ**渡されたら、作業フォルダに `README.md`・`01_source.md`・`02_explanation_memo.md`・`11_question_and_answer.md`・`12_LLM_prompts_as_guide.md` を作る。形は入力の種類によらず一律。

## 守ること

1. **スクリプトを書き換えない**。失敗は `REASON=` の行と標準エラーをそのまま報告して終わる。
2. **オプションは `--help` が正**。使う前に `--help` を読む。
3. **入力の Markdown を変えない**。`01_source.md` の本文（`<!-- source-body:start -->` より後ろ）は入力の複製で、一字も変えない。清書・整形・見出しの挿入はしない。
4. **本文に無いことを事実として書かない**。補足は `【補足】`、推測は `【推測】`。引用は本文から一字一句同じに。
5. **質問は Step 0 の 1 回だけ**（Q6 もそこに含める）。あとは止まらずに進める。指示から分かる項目は聞かない。
6. **最終ファイルは `assemble.py` が作る**。手で写さず、直すときは `out/` の元のファイルを直して `assemble.py` をやり直す。
7. 「合格」と書けるのは、確認結果を示せるときだけ。検査を通すために字数・期待値・検査の側を書き換えない。

`<RUN>` と `<SKILL_DIR>`: `<SKILL_DIR>` はこの `SKILL.md` があるフォルダ。`<RUN>` は、`uv` があれば `uv run --python 3.12`、なければ `python3`（3.10 以上）。

## Step 0：環境と事前確認（最初の 1 回だけ）

使い方を聞かれただけのとき（下のモード表の最終行）は、Step 0 を行わず、`workflows/help.md` で答えて終える。作業フォルダが既にある続き・作り直しは、聞く項目が少ない（既にある答えは `out/00_run-report.md` にある）。

1. **環境**: `<RUN> <SKILL_DIR>/scripts/scaffold.py --help` が動くか確かめる。動かない（コードが実行できない）ときは、最初に「形の検査は機械では行えない」と伝える。
2. **入力**: Markdown のパスが 1 つあるか。URL だけなら `ced-url-to-md` を案内して終える（`NO_INPUT`）。2 つ以上なら 1 つずつ頼む（`MULTI_SOURCE`）。
   作業フォルダが既にあるかは、`<RUN> <SKILL_DIR>/scripts/scaffold.py <入力> --dry-run` で（何も書かずに）確かめる。`DEST_EXISTS` なら、Q6 を次の質問にまとめる。
3. **聞くこと**（入力と指示から分からない項目だけ。1 回に最大 4 つ。**日本語の選択式**で）:

| # | 確かめること | 聞かなかったときの既定 |
|---|---|---|
| Q1 | 作業フォルダの場所と名前 | 今いるフォルダの直下の `YYMMDD_<名前>/`（日付は実行した日。名前は入力のファイル名を、英小文字・数字・`-` の 40 文字以内にしたもの。英字が無ければ `source`。スライドは、その直下の `docs/` に置く） |
| Q2 | 読み手と目的 | 自分の学習・実務への応用 |
| Q3 | 内容の種類（`references/content-types.md`） | 自動で判定（自信が無いときだけ聞く） |
| Q4 | グループ分け | 推奨の 1 案を採る（3 案の提案はしない） |
| Q5 | 本文に無い補足（一般知識・例）を足すか | 足す。必ず印を付ける。Web 検索はしない |
| Q6 | 同名のフォルダがあるとき（`DEST_EXISTS`） | **既定を置かず聞く**（続きから／別名／やめる） |

「一気通貫で」「質問なしで」と言われたら、Q6 以外は聞かず、採った既定を `out/00_run-report.md` に書く。
「不明点は最初に質問して」と言われたときも、**表の項目のうち入力と指示から分からないものだけ**を聞く（全部が分かるなら質問は 0 回でよい。聞いたことは `run-report` に残す）。

**聞くかどうかの基準**（件数がぶれないように）: 聞くのは、入力と指示から決められず、**答えで出来上がりが変わる**項目だけ。
- Q2（読み手と目的）・Q5（補足を足すか）: 指示に無ければ聞く。
- Q1: 指示に場所の指定が無ければ**聞かず**既定。今いるフォルダに作れない事情があるときだけ聞く。
- Q3: 自動判定に自信があれば聞かない。Q4: 聞かない（グループ分けの希望が指示にあれば従う）。
- 既定を採った項目は、聞かなかった理由と一緒に `run-report` に書く。

## モード

| 頼まれたこと | 読むファイル |
|---|---|
| 解説メモを作って（一気通貫） | `workflows/ingest.md` → `workflows/analyze.md` → `workflows/assemble.md` → `workflows/review.md` |
| 取り込みだけ（フォルダと冒頭を作る） | `workflows/ingest.md` |
| 「Phase N だけ」「FAQ だけ」などの部分実行 | `workflows/analyze.md`（部分実行・再実行の節） |
| 続きから・「<ステップ>を作り直して」（作業フォルダが既にある） | `workflows/analyze.md`（部分実行・再実行の節）。先に `scaffold.py <作業フォルダ>` で状態を見る |
| 転記だけ（`out/` はできている） | `workflows/assemble.md` → `workflows/review.md` |
| 検査だけ・完了報告だけ | `workflows/review.md` |
| 使い方を聞かれた（作らない） | `workflows/help.md` |

**一気通貫の流れ**: Step 0 → 取り込み → 解説の生成（`out/02`〜`11`）→ 転記（`assemble.py`。手で写さない）→ 検査と読み合わせ（合格まで。3 回まで）→ 完了報告。完了報告には `check_docs.py` の結果を必ず入れる。

取り込みで、プロファイル（`video`・`article`・`document`）の文書を **1 ファイルだけ**読む（`references/profiles/`）。入力の決まりは `references/input-contract.md`、出力の形は `references/output-formats.md`、内容の種類は `references/content-types.md`、プロンプトは `references/prompt-templates.md`（ステップごとに該当の節だけ）。

## 失敗したとき

標準エラーの最後の 3 行（`[stop]`・`[next]`・`REASON=<コード>`）をそのまま伝える。

| REASON | 動き |
|---|---|
| `NO_INPUT` | 終了。パスを確かめてもらう（URL なら `ced-url-to-md`） |
| `EMPTY_CONTENT` | 終了。入力を確かめてもらう |
| `MULTI_SOURCE` | 終了。1 つずつ頼んでもらう |
| `MISSING_OUT_FILE` | 足りない `out/` のファイル・見出しを作る（該当する Step を実行）→ `assemble.py` をやり直す |
| `CHECK_FAILED` | 不合格の項目を `out/` で直して `assemble.py` をやり直す（3 回まで。残れば完了報告に書く） |
| `DEST_EXISTS` | Q6 の答えに従う（続きから／別名／やめる） |
| `UNEXPECTED` | スクリプトは直さず、標準エラーを添えて報告して終了 |

frontmatter が無い・項目が欠けているのは**失敗ではない**（警告を出して続ける）。

## スクリプトを実行できないとき（Claude.ai でコード実行が使えない設定など）

Step 0 の 1 で `scaffold.py --help` が動かなかったとき。作業フォルダは作れないので、最終ファイル 5 本を**ファイルとして**出す（ファイルが作れなければ、ファイルごとの独立した Markdown のブロック）。

1. 最初に「形の検査は機械では行えません。完了報告に『機械での検査は未実施』と書きます」と伝える。質問は Step 0 と同じ（Q6 は該当しない）。
2. `01_source.md`: 入力の frontmatter を除いた本文を、**一字も変えずに**貼る。冒頭（題名・出典・要約・目次・`<!-- source-body:start -->`）は `references/output-formats.md` の 2-2 とひな形（`assets/templates/`）のとおり。
3. 解説の生成は `workflows/analyze.md` と同じ（`out/` のファイルは会話の中で作ってよい。`out/` のフォルダ・`00_manifest.json` は作らない）。
4. 転記は、`assemble.py` の代わりに `references/output-formats.md` の「4. 転記表」を見て行う。見出し・文字数の決まりは同じ文書の 2・5。
5. 検査は、`references/self-review.md` の検査項目と読み合わせ R-1〜R-4 を**目で**確かめる。完了報告の「検査」の行は「機械での検査は未実施。目で確かめた項目：…」とし、「合格」とは書かない（守ること 7）。

## 関連スキル

- `ced-url-to-md`（前の工程）: URL やファイルを Markdown にする。このスキルは URL を取得しない。
- `ced-websearch-slide-ja`（後の工程）: 解説スライドにする。このスキルは呼ばない。
- `globis-course-deepdive`: 講座フォルダ専用の別スキル。起動の言い回しで使い分ける（このスキルは講座フォルダを対象にしない）。
