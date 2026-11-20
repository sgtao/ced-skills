# tests/fixtures/ — 見本（P0: inputs/ の入力 6 種）

すべて自作の架空の内容（著作物・GLOBIS の字幕は入れない）。frontmatter は `url-to-md` の
`add_frontmatter.py` で付けたもの（`--retrieved-at` は固定）。項目の正は `add_frontmatter.py --help`。

| `inputs/` のファイル | 種類（プロファイル） | ねらい |
|---|---|---|
| `video.md` | video（`source_format: youtube`） | 句読点なし・誤変換あり・`**[MM:SS]**` つき。概要欄にチャプターあり |
| `video-nochapter.md` | video | `video.md` からチャプターを除いたもの。スキルが区切りを付ける場合 |
| `article.md` | article（`source_format: html`） | 見出し 4 つ・コードブロック 1 つ・表 1 つ |
| `document.md` | document（`source_format: pdf`、`conversion: pdf`） | PDF 経由。表と SVG の図あり（`has_figures: true`） |
| `document-direct.md` | document（`source_format: pptx`、`conversion: direct`） | 直接変換。`<!-- Slide number: N -->`、末尾に「補足」。図形が再現されていない |
| `plain.md` | （frontmatter なし） | 項目が欠けていても止まらないこと。`##` 見出しが無い短い入力 |

## `video.md`・`video-nochapter.md` に入れた誤変換（意図したもの）

清書は v0.1.0 では行わない（複製のまま）。後の改修で清書を足すときの確認用に、場所を控える。

| 入っている語 | 正しい語 |
|---|---|
| 在庫回転立 | 在庫回転率 |
| 月症 | 月商 |
| 減価率 | 原価率 |
| 店卸し | 棚卸し |
| 初注点 | 発注点 |

## 数値（読み合わせ用）

月商 300 万円 × 原価率 60% = 売上原価 180 万円。平均在庫 90 万円（月初 100・月末 80）で、回転率は 2 回。30 日 ÷ 2 = 15 日分。

## `golden/`（合格する作業フォルダの見本）

| フォルダ | 作り方 | 入力 |
|---|---|---|
| `golden/video/` | P1 で**手作り**。02・12・README の一部は P4 で `assemble.py` の出力に置き換えた | `inputs/video.md` |
| `golden/article/`・`golden/document/`・`golden/document-direct/` | P5 の通し実行（新しいサブエージェントが `SKILL.md` を入口に最初から最後まで実行）の**出力そのまま**。`out/00_manifest.json` の入力パスと `out/00_run-report.md` の絶対パスだけ、相対に直した | `inputs/article.md`・`document.md`・`document-direct.md` |

`article`・`document`・`document-direct` の中身は LLM が書いたもの（`skill_version: 0.0.4` の版で実行）。テストは形の検査（`check_docs.py`）・転記の再現・本文の保全を確かめるだけで、文面の良し悪しは確かめない。
