#!/usr/bin/env python3
"""merge_hooks.py — プラグインの hooks.json を ~/.claude/settings.json に足す／外す（install-local.sh から呼ばれる）。

使い方:
    python3 merge_hooks.py <settings.json> <hooks.json> <skill_dir>   # 足す（既存の ja-output-quality 分は置き換え）
    python3 merge_hooks.py --remove <settings.json>                   # 外す

hooks.json の中の ${CLAUDE_PLUGIN_ROOT}/skills/ja-output-quality を skill_dir に置き換える。
この仕組みが足したフックかどうかは、command か prompt か statusMessage に MARK が含まれるかで見分ける。
"""
import json
import sys
from pathlib import Path

MARK = "ja-output-quality"
MARK2 = "日本語チェック"


def _is_ours(h: dict) -> bool:
    s = json.dumps(h, ensure_ascii=False)
    return MARK in s or MARK2 in s


def _strip(settings: dict) -> dict:
    hooks = settings.get("hooks") or {}
    for event in list(hooks.keys()):
        kept = []
        for group in hooks[event]:
            inner = [h for h in (group.get("hooks") or []) if not _is_ours(h)]
            if inner:
                group = dict(group); group["hooks"] = inner; kept.append(group)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event)
    if hooks:
        settings["hooks"] = hooks
    else:
        settings.pop("hooks", None)
    return settings


def load(p: Path) -> dict:
    if not p.exists() or not p.read_text(encoding="utf-8").strip():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--remove":
        p = Path(args[1]); s = _strip(load(p))
        p.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"settings.json から ja-output-quality のフックを外しました: {p}")
        return 0
    settings_path, hooks_path, skill_dir = Path(args[0]), Path(args[1]), args[2]
    raw = hooks_path.read_text(encoding="utf-8").replace("${CLAUDE_PLUGIN_ROOT}/skills/ja-output-quality", skill_dir)
    add = json.loads(raw)["hooks"]
    settings = _strip(load(settings_path))
    hooks = settings.setdefault("hooks", {})
    for event, groups in add.items():
        hooks.setdefault(event, []).extend(groups)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"settings.json に ja-output-quality のフックを足しました: {settings_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
