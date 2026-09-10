#!/usr/bin/env python3
"""office_text.py — PowerPoint / Excel / Word から本文を抜き出し、日本語の機械チェックにかける（標準ライブラリだけ）。

使い方:
    python3 office_text.py <file.pptx|.xlsx|.docx>               # 本文を標準出力へ
    python3 office_text.py <file> --lint [--customer] [--json]   # 抜き出して ja_lint にかける
    python3 office_text.py --hook                                # PostToolUse(Bash) フック

フックの動き:
    標準入力のフック JSON から Bash コマンドを読み、コマンドに含まれる .pptx/.xlsx/.docx の
    パスのうち、直近20分以内に更新されたファイルを検査する。本文を抜き出して一時ファイルに
    保存し、ja_lint で warn 以上の指摘があれば要約を stderr に出して exit 2 で返す
    （Claude に指摘が戻る）。該当ファイルがない、抜き出せない、エラーのときは exit 0（素通し）。
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import tempfile
import time
import zipfile
from pathlib import Path

OFFICE_EXT = (".pptx", ".xlsx", ".docx")
PATH_RE = re.compile(r"[\w./\\~:-]+\.(?:pptx|xlsx|docx)\b", re.I)


def _texts(xml: str, tag: str) -> list[str]:
    return [html.unescape(m) for m in re.findall(rf"<{tag}(?:\s[^>]*)?>(.*?)</{tag}>", xml, flags=re.S)]


def _num(name: str) -> int:
    m = re.search(r"(\d+)\.xml$", name)
    return int(m.group(1)) if m else 0


def extract(path: str) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    out: list[str] = []
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        if ext == ".pptx":
            for n in sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=_num):
                xml = z.read(n).decode("utf-8", "replace")
                lines = ["".join(_texts(par, "a:t")) for par in re.findall(r"<a:p>(.*?)</a:p>", xml, flags=re.S)]
                out.append(f"# スライド {_num(n)}")
                out += [l for l in lines if l.strip()]
            for n in sorted((n for n in names if re.match(r"ppt/notesSlides/notesSlide\d+\.xml$", n)), key=_num):
                xml = z.read(n).decode("utf-8", "replace")
                lines = ["".join(_texts(par, "a:t")) for par in re.findall(r"<a:p>(.*?)</a:p>", xml, flags=re.S)]
                lines = [l for l in lines if l.strip() and not l.strip().isdigit()]
                if lines:
                    out.append(f"# ノート {_num(n)}")
                    out += lines
        elif ext == ".xlsx":
            shared: list[str] = []
            if "xl/sharedStrings.xml" in names:
                xml = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
                shared = ["".join(_texts(si, "t")) for si in re.findall(r"<si>(.*?)</si>", xml, flags=re.S)]
            for n in sorted((n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n)), key=_num):
                xml = z.read(n).decode("utf-8", "replace")
                out.append(f"# シート {_num(n)}")
                for c in re.finditer(r"<c\b([^>]*)>(.*?)</c>", xml, flags=re.S):
                    attrs, body = c.group(1), c.group(2)
                    t = re.search(r'\bt="(\w+)"', attrs)
                    kind = t.group(1) if t else None
                    if kind == "s":
                        v = re.search(r"<v>(\d+)</v>", body)
                        if v and int(v.group(1)) < len(shared):
                            out.append(shared[int(v.group(1))])
                    elif kind == "inlineStr":
                        out.append("".join(_texts(body, "t")))
                    elif kind == "str":
                        v = re.search(r"<v>(.*?)</v>", body, flags=re.S)
                        if v:
                            out.append(html.unescape(v.group(1)))
        elif ext == ".docx":
            xml = z.read("word/document.xml").decode("utf-8", "replace")
            for par in re.findall(r"<w:p\b.*?</w:p>", xml, flags=re.S):
                line = "".join(_texts(par, "w:t"))
                if line.strip():
                    out.append(line)
        else:
            raise ValueError(f"対応していない拡張子: {ext}")
    return "\n".join(l for l in out if l is not None)


def lint_extracted(path: str, text: str, customer: bool) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ja_lint  # noqa: E402
    return ja_lint.lint_text(path, text, customer=customer)


def _save_text(text: str, src: str, base_dir: str | None) -> str:
    d = Path(base_dir or tempfile.gettempdir()) / "ja-output-quality"
    d.mkdir(parents=True, exist_ok=True)
    out = d / (Path(src).name + ".txt")
    out.write_text(text, encoding="utf-8")
    return str(out)


def run_hook() -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""
    cwd = data.get("cwd") or os.getcwd()
    seen: list[str] = []
    for m in PATH_RE.findall(command):
        cand = os.path.expanduser(m)
        if not os.path.isabs(cand):
            cand = os.path.join(cwd, cand)
        cand = os.path.normpath(cand)
        if cand in seen or not os.path.isfile(cand):
            continue
        if time.time() - os.path.getmtime(cand) > 20 * 60:
            continue
        seen.append(cand)
    if not seen:
        return 0
    messages: list[str] = []
    for f in seen:
        try:
            text = extract(f)
        except Exception as e:  # 抜き出せないファイルは素通し
            messages.append(f"- {f}: 本文を抜き出せませんでした（{e}）。手動で確認してください")
            continue
        if len(re.sub(r"\s", "", text)) < 50:
            continue
        saved = _save_text(text, f, data.get("scratchpad_dir"))
        try:
            result = lint_extracted(f, text, customer=True)
        except Exception as e:
            messages.append(f"- {f}: 機械チェックを実行できませんでした（{e}）。抜き出した本文: {saved}")
            continue
        s = result["summary"]
        if s["critical"] + s["warn"] == 0:
            messages.append(f"- {f}: 機械チェックの warn は 0 件。抜き出した本文: {saved}（顧客に渡すなら /ja-output-quality review でレビューする）")
            continue
        top = [x for x in result["findings"] if x["severity"] != "info"][:8]
        lines = [f"- {f}: warn 以上が {s['critical'] + s['warn']} 件。原稿を直して作り直すこと。抜き出した本文: {saved}"]
        lines += [f"    L{x['line']} {x['rule']}: {x['excerpt']} → {x['detail']}" for x in top]
        messages.append("\n".join(lines))
    if not messages:
        return 0
    body = "ja-output-quality（生成した文書の本文チェック）\n" + "\n".join(messages)
    if any("warn 以上が" in m for m in messages):
        print(body, file=sys.stderr)  # exit 2 で Claude に戻す
        return 2
    # 指摘なし: 抜き出した本文の場所だけを additionalContext で知らせる（exit 0 の stderr は表示されない）
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": body}}, ensure_ascii=False))
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--hook" in args:
        try:
            return run_hook()
        except Exception:
            return 0
    if not args:
        print(__doc__)
        return 1
    path = args[0]
    if not os.path.isfile(path):
        print(f"error: {path} が見つかりません", file=sys.stderr)
        return 1
    text = extract(path)
    if "--lint" not in args:
        print(text)
        return 0
    result = lint_extracted(path, text, customer="--customer" in args)
    if "--json" in args:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ja_lint
        print(ja_lint.render_text(result, None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
