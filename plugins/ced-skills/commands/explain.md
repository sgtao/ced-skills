---
description: URL・ファイル・YouTube から、解説メモと解説スライド（MD・HTML）を 1 度の指示で作る
argument-hint: <URL または ファイルのパス> [--out <出力フォルダ>] [--slides <枚数>] [--audience <読み手>]
allowed-tools: Skill, Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion
---

# /ced-skills:explain — 解説メモと解説スライドを作る

入力: $ARGUMENTS

## 手順

### 1. 入力と答えをそろえる
- 引数に、出力先（`--out`）、枚数（`--slides`）、読み手（`--audience`）のいずれかが無いときだけ、
  **AskUserQuestion を 1 回だけ**呼ぶ（4 問以内。出力先・読み手・スライド枚数の順）。
  選択肢と質問文は日本語で書く。
- 引数で答えを渡されたものは聞かない。すべて引数で揃っていれば、AskUserQuestion は呼ばない。
- 入力（URL かファイル）が無いときは、それだけを 1 行で尋ねて止まる。

### 2. 入力を Markdown にする
- `ced-url-to-md` のスキルを使い、入力を Markdown に変換する（YouTube は字幕、PDF は `ced-pdf-to-md-ja` に委譲される）。
- 変換できないときは、理由を報告して終わる。

### 3. 解説メモを作る
- `ced-craft-explanation-docs` のスキルを使い、手順 2 の Markdown を 1 つ渡して解説メモ一式を作る。
- 出力先は手順 1 で決めたフォルダ。

### 4. 解説スライドを作る
- `ced-websearch-slide-ja` のスキルを使い、解説メモをもとにスライド MD を書く（指定の枚数に合わせる）。
- スライド MD を `mdss-convert --json-only` にかけ、`lint` 配列の error と warn を直す。
  直したあとの error と warn が 0 になるまで繰り返す（同じ方法で 2 回直せなかったら、残りを報告する）。
- lint が通ったスライド MD から HTML を作る。`.md` と `.html` を同じフォルダに置く。

### 5. 報告する
- 作ったファイルのパス、lint の結果（error／warn の数）、未検証のこと（画像の確認など）を 5 行以内で書く。
- 次の一手として 1 行だけ提案してよい（依頼にない機能は足さない）。
