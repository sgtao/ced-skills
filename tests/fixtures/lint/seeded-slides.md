---
title: プラグインで配る Claude Code スキルの仕組み
palette: neon
purpose: self-study
---
<!-- slide: title -->
# プラグインで配る<br>Claude Code スキルの仕組み
subtitle: Claude Code を始めたばかりの人のための 5 分解説
badges: [スキル, プラグイン, マーケットプレイス]
---
<!-- slide: points -->
badge: 基本
## スキルは ==フォルダ と SKILL.md== の組
lead: SKILL.md の先頭に name と description を書く
- **name**：スキルの名前
- **description**：ここに書いた言葉を含む依頼が来ると、Claude がそのスキルを読み込む
- **scripts/**：決まった処理を行う補助スクリプトを置く
point: 読み込まれるかどうかは description の言葉で決まる
note: 【補足】自分が実際に頼むときの言い回しを description に入れておくと、狙いどおりに読み込まれやすくなる。
---
<!-- slide: tabel -->
badge: 構造
## ==配る単位== と ==使う単位== を分ける
lead: 小さい単位を、大きい単位が包む

```
| 層 | ファイル | 役割 |
|---|---|---|
| マーケットプレイス | .claude-plugin/marketplace.json | 配布のための目録（リポジトリ直下） |
| プラグイン（配る単位） | .claude-plugin/plugin.json | プラグインの名前と版 |
| スキル・コマンド（使う単位） | SKILL.md | 名前と説明、手順 |

point: 配る・版を管理するのはプラグイン、呼ぶのはスキルとコマンド
note: marketplace.json はリポジトリ直下の .claude-plugin/ に置く。プラグインの中身は plugins の下のフォルダに置く。
---
<!-- slide: steps -->
badge: 手順
## 使う側は ==3 ステップ==
lead: マーケットプレイスを追加し、プラグインを入れ、名前空間付きで呼ぶ
```steps
style: cards
items:
  - icon: "🏪"
    title: マーケットプレイスを追加
    desc: 配布の目録を読み込む
  - icon: "📦"
    title: プラグインを入れる
    desc: スキルとコマンドがまとめて入る
  - icon: "⌨️"
    title: 名前空間付きで呼ぶ
    desc: 例 /ced-skills:explain
    tone: outline
```
point: コマンドは「プラグイン名:コマンド名」で打つ
note: 【補足】追加と導入は Claude Code の /plugin コマンドで行う。具体的な打ち方は記事には書かれていないので、公式ドキュメントで確かめる。
---
<!-- slide: points -->
badge: 注意
## 名前の衝突は ==接頭辞== で防ぐ
lead: 同じ言葉で反応するスキルが複数あると、どれが読み込まれたかが分かりにくい
- **起きること**：思ったスキルが読み込まれず、原因にも気づきにくい
- **対策**：配布するスキルには接頭辞を付けて名前を区別する（例 ced-）
- **点検**：入れているスキルの description を並べ、言葉の重なりを見る
point: 配るスキルには接頭辞を付ける
note: 記事は接頭辞を「勧められる」と述べるだけで、必須かどうかや、衝突時にどれが優先されるかは書かれていない。
---
<!-- slide: sources -->
## 出典
- [ユーザー提供](#) — 記事「プラグインで配る Claude Code スキルの仕組み」（input.html）と、その解説メモ（explained/）に基づく
