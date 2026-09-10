# 他のスキルとのつなぎ方 — 追記する文面

方針：体裁スキルは体裁の唯一のルールのまま。このスキルは体裁に触れない共通ルール（根拠との釣り合い、作業報告の排除、確度の書き分け、自然な日本語、言葉遣い）と、書き手とは別のレビューだけを足す。各スキルの SKILL.md の末尾（または「適用範囲」の節）に以下を追記する。

## customer-qa-style

「適用範囲と優先関係」の末尾に追記：

```
- 例外として ja-output-quality は併用する。同スキルは段落型／箇条書き型といった体裁に触れず、主張と根拠の釣り合い、作業報告の排除、確度の書き分け、自然な日本語、敬語の型だけを決めているため、本スキルの体裁と衝突しない。衝突したときは本スキルの体裁ルールが優先し、根拠との釣り合いと作業報告の排除は ja-output-quality が優先する。
```

「Step 5. セルフチェック」の冒頭に追記：

```
以下のチェックは書き手自身では行わない。ja-output-quality のレビュー（顧客向けは full、社内の一次回答は quick）を実行し、このチェックリストを観点B に渡す追加の観点とする。書き手は観点A・B・C の指摘を判断台帳にまとめ、決まった直し方で直す。特に「条件のない『できる』」「幅のない数値」「要確認のない未確認事項」は観点B に列挙させたほうが漏れない（`scripts/ja_lint.py` の dekiru_without_condition / bare_number / unlabeled_unverified が機械側の一次候補を出す）。
```

## natural-japanese

「4. 検査(2)」の末尾に追記：

```
フルモードの三つのレビュー（構造、読みやすさ、doctype 照合）に加えて、ja-output-quality の観点B（根拠: 確度の種類、根拠の所在、一般化しすぎ、断定とぼかしの釣り合い）を4本目の並列サブエージェントとして回す。クイックモードでは観点A・B・C をまとめた1体で足りる。顧客向け文書では lint.py に加えて `ja_lint.py --customer` を回し、敬語、作業報告の混入、確信度のぼかし、文字種の指摘を同じ判断台帳に載せる。
```

## japanese-tech-writing

末尾に追記：

```
## 別コンテキストのレビュー

書き上げた原稿は、ja-output-quality の観点A（文の要否）と観点B（根拠）を別コンテキストで通す。本規範の「論証の厳密さ」「LLM っぽい表現の禁止」は観点A・B の判定基準として渡し、書き手自身の点検で代用しない。
```

## dbx-sf-compare、presidential-brief、persol-design-format-v3、doc-coauthoring、ctx-snapshot など、日本語の成果物を出すスキル

末尾に追記（共通）：

```
## 出力品質

本文は ja-output-quality の10か条（結論先行、根拠との釣り合い、作業報告の排除、一文に役割一つ、確度の書き分け、数値の条件と幅、最初から日本語で書く、厚みの差、飾りの抑制、言葉遣い）に従って書く。顧客や経営層に渡す成果物は、書き終えたら ja-output-quality のレビュー（quick）を通し、観点B の不合格が残る状態で出さない。
```

## CLAUDE.md（Claude Code）と claude.ai の個人設定

`assets/global-rules.md` の内容を貼る。スキルが起動しない短い回答にも効く。

## 任意：Claude Code のフック（ローカルだけ）

Markdown を書き出すたびに機械チェックを自動で回す。`~/.claude/settings.json` に追記（パスは環境に合わせる。update-config スキルで設定してもよい）：

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

`--hook` モードは、標準入力のフック JSON から `tool_input.file_path` を読み、拡張子が `.md` のときだけ検査する。warn 以上の指摘があれば要約を stderr に出して exit 2 で返す（Claude に指摘が戻る）。なければ exit 0 で何も出さない。成果物以外の Markdown（メモ、ログ）にも反応するので、うるさければ matcher を外すか、対象フォルダで絞る。
