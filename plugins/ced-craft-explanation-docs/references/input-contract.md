# 入力の決まり

このスキルが受け取る入力と、frontmatter の読み方。読み取りは `scripts/_common.py` の `parse_frontmatter` の 1 か所だけ。

## 受け取るもの

| 渡し方 | 扱い |
|---|---|
| `ced-url-to-md` が作った Markdown のパス（1 つ） | **基本の形**。frontmatter を読み、作業フォルダを作る（`scaffold.py`） |
| frontmatter の無い Markdown | 受け取る。題名は本文の最初の `# ` から、プロファイルは本文の形から決める。分からない項目は書かず、`out/00_run-report.md` に「frontmatter なし」と残る。止まらない |
| `README.md` と `01_source.md` が既にあるフォルダ | そのフォルダを使う（作り直さない）。`scaffold.py <フォルダ>` は状態を返すだけで何も書かない。`01_source.md` の冒頭が足りなければ足し、**スキルが作っていない節は変えない** |
| チャットに貼られた文章 | 一度ファイルに保存してから、そのファイルを渡す（入力は Markdown のファイル） |
| URL だけ | **取得しない**。`ced-url-to-md` で先に Markdown にするよう案内して終える（`NO_INPUT`） |
| Markdown が 2 つ以上 | v0.1.0 では扱わない。1 つずつ頼むよう案内して終える（`MULTI_SOURCE`） |

## frontmatter から読む項目

項目の正は `ced-url-to-md` の `add_frontmatter.py --help`。**ここに載っている項目だけ**を読む（知らない項目は無視する）。

| 項目 | 使い道 |
|---|---|
| `title` | 作業フォルダ内の題名（無ければ本文の最初の `# `、それも無ければファイル名） |
| `source_url` | `url`（`http://`・`https://` で始まるときだけ。手元のファイルのパスは出さない） |
| `source_format` | **プロファイルの判定**（下表） |
| `conversion` | `direct`・`model-read` のとき、図は再現されていない。README の概要と解説の注意に書く |
| `has_figures` | 図を根拠にした解説を書いてよいかの目安 |
| `summary` | `01_source.md` の要約の**下書き**。本文を読んで確かめてから使う（そのまま写さない） |
| `retrieved_at` | 取得日 |
| `channel`・`published`・`duration` | 動画のときだけ。README と `01_source.md` に載せる |

| `source_format` | プロファイル | 読むファイル |
|---|---|---|
| `youtube` | `video` | `references/profiles/video.md` |
| `html` | `article` | `references/profiles/article.md` |
| `pdf`・`docx`・`pptx`・`xlsx` | `document` | `references/profiles/document.md` |
| `text`・`code`（v0.0.2：テキスト・コードの入力） | `article` | `references/profiles/article.md` |
| `subtitle`（v0.0.2：字幕ファイル `.vtt`・`.srt`） | `video` | `references/profiles/video.md` |

frontmatter が無いときの推定（`scaffold.py` が行う）: 段落頭の `**[MM:SS]**` が 3 つ以上 → `video`／`<!-- Slide number: N -->` か `<!-- page N -->` が 2 つ以上 → `document`／それ以外 → `article`。推定したときは理由が `profile_reason` に出る。

## 止まるとき・止まらないとき

- **止める**（理由コード）: `NO_INPUT`（ファイルが無い・URL）／`EMPTY_CONTENT`（本文が 30 字未満）／`MULTI_SOURCE`／`DEST_EXISTS`（作業フォルダが既にある。何も書かない）
- **止めない**: frontmatter が無い・項目が欠けている（警告を出して続ける）

## 作業フォルダの名前と場所

- 既定: 今いるフォルダの直下に `YYMMDD_<名前>/`（explain の形と同じ。日付は実行した日。名前は入力のファイル名（拡張子なし）を、英小文字・数字・`-`、40 文字以内にしたもの。英字が無ければ `source`）。解説スライドは、この直下の `docs/` に置く
- 指示で場所・名前を指定されたら `--dest` で渡す
- 既に同じ名前があるときは上書きしない（`DEST_EXISTS`）。続きから行うか、別の名前にするか、やめるかは、ユーザーに聞く
