# ja-output-quality

日本語で書く成果物に共通する品質ルールと、書き手とは別のサブエージェントによるレビューのスキル。対象は主に、IT・SI・プリセールスの現場で顧客に渡す技術回答、提案書、報告書と、その周辺の社内文書。体裁は他のスキル（customer-qa-style、natural-japanese など）に任せ、どんな体裁でも守るべきルール（根拠との釣り合い、作業報告の排除、確度の書き分け、読みやすさ、自然な日本語、言葉遣い）と、書き手から切り離したレビューだけを扱う。

## 構成

```
ja-output-quality/
├── SKILL.md                      前提、書く前のルール10か条、レビューの要点、他スキルとのつなぎ方
├── references/
│   ├── review-protocol.md        観点A/B/C のサブエージェント用プロンプトと、書き手側のまとめ方、判定の例
│   └── ja-surface.md             参照先、翻訳調の代表例、直訳の造語の言い換え、顧客向け敬語の型、文字種と記号
├── assets/
│   ├── global-rules.md           CLAUDE.md、claude.ai の個人設定に貼る短縮版ルール
│   └── integration.md            他スキルの SKILL.md に追記する文面、任意のフック設定
└── scripts/
    ├── ja_lint.py                機械チェック（標準ライブラリだけ）。敬語、作業報告の混入、確信度、条件のない「できる」、文字種
    └── fixtures/                 動作確認用のサンプル3本
```

プラグイン版には `agents/` にレビュー担当（reviewer、check-sentences、check-evidence、check-wording）が同梱され、Sonnet 5、effort max に固定されている。レビューはセッションのモデルを引き継がない。

## 導入

1. **スキルとして登録**：このフォルダを zip にして claude.ai の「スキル」設定からアップロードする（他の自作スキルと同じ手順）。Claude Code では、プラグインのマーケットプレイス経由で入れる（リポジトリの README を参照）。
2. **常に効かせるルールを貼る**：`assets/global-rules.md` の内容を `~/.claude/CLAUDE.md` と claude.ai の個人設定に貼る。スキルが起動しない短い回答にも効く。
3. **他スキルに追記する**：`assets/integration.md` の文面を customer-qa-style、natural-japanese、japanese-tech-writing、その他日本語の成果物を出すスキルに追記する。
4. **（任意）フック**：Claude Code で Markdown を書くたびに `ja_lint.py --hook` を回す設定を `assets/integration.md` のとおりに入れる。

## 使い方

```
/ja-output-quality full review 回答案.md      # 顧客向け。観点A/B/C を並列 + 2回
/ja-output-quality quick review メール.md      # 社内、日常。レビュー担当1体 + 1回
/ja-output-quality write 顧客向けの回答を作る    # ルールで書き、書き終えたら自動で review
python3 scripts/ja_lint.py 文書.md [--json] [--customer] [--baseline prev.json]
```

## 動作確認

```
cd scripts
python3 ja_lint.py fixtures/customer-smelly.md --customer    # 多数の warn/info が出る
python3 ja_lint.py fixtures/customer-natural.md --customer   # ほぼ出ない（箇条書き型は bullet_dominant の info だけ）
python3 ja_lint.py fixtures/report-natural.md                # 出ない
```

## 設計の要点

- ルールは増やすほど守られない。書く前のルールは10か条にし、残りは機械チェックと参照ファイルに逃がす。
- 書いた本人は自分の文を審査できない。レビューは別コンテキストで、書き直しの権限を与えずに行い、書き手が決まった直し方で直す。
- 主張の強さは根拠に合わせる。予防線（弱すぎ）と言い過ぎ（強すぎ）は同じ直し方（結果＋条件＋確認していない範囲）で直る。
- 最初から日本語で書く。英語で考えてから訳さない。直訳の造語を作らない。
- natural-japanese の lint.py が主、ja_lint.py はそれにない敬語、作業報告の混入、確信度、条件のない「できる」、文字種を補う。
- 同じ指摘が3文書以上で繰り返されたら、検出ルールではなく書く前のルール（体裁スキルの実例）に格上げする。
