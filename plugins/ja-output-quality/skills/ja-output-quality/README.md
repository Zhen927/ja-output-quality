# ja-output-quality

日本語の成果物に共通して適用する「出力の品質不変則」と「独立レビュー」のスキル。体裁は他のスキル（customer-qa-style、natural-japanese など）に任せ、どの体裁でも成り立たなければならない不変則（校准・工程排除・四分法・読者コスト・母語性・語域）と、書き手と別コンテキストで行うレビューだけを扱う。

## 構成

```
ja-output-quality/
├── SKILL.md                      原理・出力憲法10条・独立レビューの要点・接続方法
├── references/
│   ├── review-protocol.md        Lane A/B/C のサブエージェント用プロンプトと親の統合手順、判定例
│   └── ja-surface.md             委譲先・翻訳調の最頻型・顧客向け敬語の型・字形と記号
├── assets/
│   ├── global-rules.md           CLAUDE.md／claude.ai 個人設定に貼る常時適用ルール
│   └── integration.md            他スキルの SKILL.md に追記する文面、任意のフック設定
└── scripts/
    ├── ja_lint.py                決定的検出（標準ライブラリのみ）。敬語・工程叙述・確信度・校准・字形
    └── fixtures/                 動作確認用のサンプル3本
```

プラグイン版には `agents/` にレビュアー（reviewer / lane-a / lane-b / lane-c）が同梱され、Sonnet 5・effort max に固定されている。レビューはセッションのモデルを継承しない。

## 導入

1. **スキルとして登録**：このフォルダを zip にして claude.ai の「スキル」設定からアップロードする（他の自作スキルと同じ手順）。Claude Code では `~/.claude/skills/ja-output-quality/` に置く。
2. **常時適用ルールを貼る**：`assets/global-rules.md` の内容を `~/.claude/CLAUDE.md` と claude.ai の個人設定に貼る。スキルが発火しない短い回答にも効く。
3. **他スキルに接続行を足す**：`assets/integration.md` の文面を customer-qa-style、natural-japanese、japanese-tech-writing、その他日本語成果物を出すスキルに追記する。
4. **（任意）フック**：Claude Code で Markdown を書くたびに `ja_lint.py --hook` を回す設定を `assets/integration.md` の通りに入れる。

## 使い方

```
/ja-output-quality full review 回答案.md      # 顧客向け。3 Lane 並列 + 2ラウンド
/ja-output-quality quick review メール.md      # 社内・日常。統合レビュアー1体 + 1ラウンド
/ja-output-quality write 顧客向けの回答を作る    # 憲法で書き、完成後に自動で review
python3 scripts/ja_lint.py 文書.md [--json] [--customer] [--baseline prev.json]
```

## 検証

```
cd scripts
python3 ja_lint.py fixtures/customer-smelly.md --customer    # 多数の warn/info が出る
python3 ja_lint.py fixtures/customer-natural.md --customer   # ほぼ出ない（箇条書き型は bullet_dominant の info だけ）
python3 ja_lint.py fixtures/report-natural.md                # ほぼ出ない
```

## 設計の要点

- 規則は増やすほど守られない。生成時の制約は10条に圧縮し、残りは機械検出と参照ファイルに逃がす。
- 書いた本人は自分の文を審査できない。レビューは別コンテキストで、書き直し権限なしで行い、親が固定操作で直す。
- 主張の強さ＝証拠の強さ。過度防御（弱すぎ）と証拠越境（強すぎ）は同じ操作（結果＋境界＋未検証範囲）で直る。
- natural-japanese の lint.py が主、ja_lint.py はそれに無い敬語・工程叙述・確信度・校准・字形を補う。
- 同じ finding が3文書以上で再発したら、検出規則ではなく生成時の制約（体裁スキルの実例）へ昇格させる。
