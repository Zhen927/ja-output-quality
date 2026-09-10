# 他スキルへの接続 — 追記する文面

方針：体裁スキルは体裁の唯一の規範のまま。本スキルは体裁に触れない不変則（校准・工程排除・四分法・母語性・語域）と独立レビューだけを足す。各スキルの SKILL.md の末尾（または「適用範囲」節）に以下を追記する。

## customer-qa-style

「適用範囲と優先関係」の末尾に追記：

```
- 例外として ja-output-quality は併用する。同スキルは段落型／箇条書き型といった体裁に触れず、主張と証拠の校准・工程の記述の排除・事実と推測の区別・母語性・敬語の型だけを規定するため、本スキルの体裁と衝突しない。衝突したときは本スキルの体裁規定が優先し、校准と工程排除は ja-output-quality が優先する。
```

「Step 5. セルフチェック」の冒頭に追記：

```
以下のチェックは書き手自身では行わない。ja-output-quality の独立レビュー（顧客向けは full、社内の一次回答は quick）を実行し、このチェックリストを Lane B の追加観点として渡す。書き手は Lane A/B/C の所見を判断台帳に統合し、固定操作で直す。特に「制約ゼロの『できる』」「幅のない数値」「要確認のない未確認事項」は Lane B に列挙させたほうが漏れない（`scripts/ja_lint.py` の dekiru_without_condition / bare_number / unlabeled_unverified が機械側の一次候補を出す）。
```

## natural-japanese

「4. 検査(2)」の末尾に追記：

```
フルモードの三つのレビュー（構造・読みやすさ・doctype照合）に加えて、ja-output-quality の Lane B（成立性: 主張の種類・証拠の所在・外挿・強い語と弱い語の校准）を4本目の並列サブエージェントとして回す。クイックモードでは Lane A/B/C を統合した1体で足りる。顧客向け文書では lint.py に加えて `ja_lint.py --customer` を回し、敬語・工程叙述・確信度の均し・字形の findings を同じ台帳に載せる。
```

## japanese-tech-writing

末尾に追記：

```
## 独立レビュー

書き上げた原稿は、ja-output-quality の Lane A（存在性）と Lane B（成立性）を別コンテキストで通す。本規範の「論証の厳密さ」「LLM っぽい表現の禁止」は Lane A/B の判定基準として渡し、書き手自身の点検で代用しない。
```

## dbx-sf-compare / presidential-brief / persol-design-format-v3 / doc-coauthoring / ctx-snapshot 等、日本語の成果物を出すスキル

末尾に追記（共通）：

```
## 出力品質

本文は ja-output-quality の出力憲法（結論先行・校准・工程排除・一文一役・四分法・数値の条件と幅・母語の統語・非均質構造・装飾抑制・語域）に従って書く。顧客や経営層に渡す成果物は、完成後に ja-output-quality の独立レビュー（quick）を通し、Lane B の FAIL が残る状態で出さない。
```

## CLAUDE.md（Claude Code）と claude.ai 個人設定

`assets/global-rules.md` の内容を貼る。スキルが発火しない短い回答にも効く。

## 任意：Claude Code のフック（ローカルのみ）

Markdown を書き出すたびに機械検出を自動で回す。`~/.claude/settings.json` に追記（パスは環境に合わせる。update-config スキルで設定してもよい）：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/ja-output-quality/scripts/ja_lint.py --hook"
          }
        ]
      }
    ]
  }
}
```

`--hook` モードは標準入力のフック JSON から `tool_input.file_path` を読み、拡張子が `.md` のときだけ検査する。warn 以上の finding があれば要約を stderr に出して exit 2 で返す（Claude に所見が戻る）。なければ exit 0 で何も出さない。成果物以外の Markdown（メモ・ログ）にも発火するので、うるさければ matcher を外すか、対象ディレクトリで絞る。
