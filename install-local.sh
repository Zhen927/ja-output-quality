#!/usr/bin/env bash
# ja-output-quality を、プラグインの仕組みを使わずに ~/.claude に直接入れる。
# VS Code 拡張・ターミナル・デスクトップアプリは同じ ~/.claude を読むので、一度入れれば全部で使える。
#
#   使い方:  bash install-local.sh            # 入れる（再実行すれば更新）
#           bash install-local.sh --remove   # 外す
#
# 入れるもの:
#   ~/.claude/skills/ja-output-quality/        スキル本体（/ja-output-quality）
#   ~/.claude/agents/ja-output-quality-*.md    レビュー担当4体（Sonnet 5 / Haiku 4.5 固定）
#   ~/.claude/settings.json の hooks           ルール再注入、書き込み前の門番、Office の本文チェック、回答の判定
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
PLUG="$ROOT/plugins/ja-output-quality"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SKILL_DEST="$CLAUDE_DIR/skills/ja-output-quality"
AGENT_DEST="$CLAUDE_DIR/agents"
SETTINGS="$CLAUDE_DIR/settings.json"

PY=""
if command -v python3 >/dev/null 2>&1; then PY=python3; elif command -v python >/dev/null 2>&1; then PY=python; fi

if [ "$1" = "--remove" ]; then
  rm -rf "$SKILL_DEST"
  rm -f "$AGENT_DEST"/ja-output-quality-*.md
  if [ -n "$PY" ] && [ -f "$SETTINGS" ]; then
    "$PY" "$ROOT/scripts/merge_hooks.py" --remove "$SETTINGS"
  fi
  echo "外しました: $SKILL_DEST, $AGENT_DEST/ja-output-quality-*.md, settings.json の hooks"
  exit 0
fi

mkdir -p "$CLAUDE_DIR/skills" "$AGENT_DEST"
rm -rf "$SKILL_DEST"
cp -r "$PLUG/skills/ja-output-quality" "$SKILL_DEST"
rm -rf "$SKILL_DEST/scripts/__pycache__"

# エージェント: プラグイン版の ja-output-quality:reviewer に対応する名前は ja-output-quality-reviewer
for f in "$PLUG"/agents/*.md; do
  base="$(basename "$f" .md)"
  dest="$AGENT_DEST/ja-output-quality-$base.md"
  sed "s/^name: $base$/name: ja-output-quality-$base/" "$f" > "$dest"
done

# フック: ${CLAUDE_PLUGIN_ROOT}/skills/ja-output-quality を実際の置き場所に置き換えて settings.json に足す
if [ -n "$PY" ]; then
  "$PY" "$ROOT/scripts/merge_hooks.py" "$SETTINGS" "$PLUG/hooks/hooks.json" "$SKILL_DEST"
else
  echo "python が見つからないので settings.json は変更していません。"
  echo "次のファイルの内容を、\${CLAUDE_PLUGIN_ROOT}/skills/ja-output-quality を $SKILL_DEST に置き換えたうえで、$SETTINGS の hooks に足してください:"
  echo "  $PLUG/hooks/hooks.json"
fi

echo "入れました。新しい Claude Code セッション（VS Code、ターミナル、デスクトップ）を開いて /skills で確認してください。"
echo "  スキル:        $SKILL_DEST"
echo "  エージェント:  $AGENT_DEST/ja-output-quality-{reviewer,check-sentences,check-evidence,check-wording}.md"
echo "  フック:        $SETTINGS"
