# ja-output-quality

日本語の成果物に共通して適用する「出力の品質不変則」と「独立レビュー」の Claude スキル。このリポジトリは Claude Code のプラグインマーケットプレイスになっており、どの PC でも一度登録すれば以後は更新が届く。

## 導入（各 PC で一度だけ）

Claude Code の中で次の二つを実行する。

```
/plugin marketplace add Zhen927/ja-output-quality
/plugin install ja-output-quality@zhen927-skills
```

導入後、スキルは `/ja-output-quality:ja-output-quality` として呼べる。日本語の顧客向け文書やレポートを書く依頼では、コマンドを打たなくても description の条件で自動的に読み込まれる。

`/skills` で一覧に出ているか確認できる。出ていなければ `/reload-plugins`。

## 更新

リポジトリに push すれば新しい版になる（version を宣言していないので、コミットが進めば更新扱い）。各 PC では次のどちらか。

- `/plugin` → Marketplaces タブで `zhen927-skills` の自動更新をオンにする（サードパーティのマーケットプレイスは既定でオフ）
- 手動なら `/plugin marketplace update zhen927-skills` のあと `/plugin update ja-output-quality@zhen927-skills`

## claude.ai（Web・アプリ）側

claude.ai のスキル設定にアップロードしたものは、claude.ai のチャットと Web 版 Claude Code（クラウドセッション）で使われる。ローカルの Claude Code とは同期されないため、ローカルは上のプラグイン導入で入れる。リポジトリを更新したときは、`plugins/ja-output-quality/skills/ja-output-quality/` を zip にして claude.ai 側も再アップロードする。

## プラグインを使わない場合

`plugins/ja-output-quality/skills/ja-output-quality/` を `~/.claude/skills/ja-output-quality/` にコピーしても動く。ただし更新は手で取り直すことになる。

## 中身

`plugins/ja-output-quality/skills/ja-output-quality/README.md` を参照。
