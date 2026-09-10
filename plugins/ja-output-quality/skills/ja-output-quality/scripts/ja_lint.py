#!/usr/bin/env python3
"""ja_lint.py — 日本語の成果物を決定的に検査する（標準ライブラリのみ）。

設計:
    検出は機械、判断は人か別コンテキストのレビュアー。findings は疑いの提示であり
    指示ではない。lint なので検出件数に関わらず exit 0。入力エラーだけ exit 1。
    --hook モード（Claude Code の PostToolUse）だけは warn 以上があれば exit 2 で
    所見を stderr に返す。

    natural-japanese の lint.py と同じ JSON 形（findings: rule/severity/line/excerpt/detail）
    を返すので、判断台帳の扱いも同じでよい。常套句・翻訳調・体言止め率・段落構造・
    語彙多様性の深い検出は lint.py（uv + sudachi）に任せ、本スクリプトは lint.py に無い
    (1) 顧客向け敬語、(2) 工程叙述・自己言及、(3) 語尾による確信度の均し、
    (4) 制約のない「できる」・幅のない数値・標識のない未確認事項、(5) 字形・記号
    を担当する。uv が使えない環境向けに常套句・翻訳調の最小集合も持つ。

使い方:
    python3 ja_lint.py <file.md> [--json] [--baseline prev.json] [--customer]
    python3 ja_lint.py --hook        # 標準入力のフック JSON から file_path を読む
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import statistics
import sys
from pathlib import Path

HAN_RE = re.compile("[一-鿿㐀-䶿]")
SENT_SPLIT_RE = re.compile(r"(?<=[。！？!?])")
LIST_RE = re.compile(r"^\s*(?:[-*+・]|\d+[.)．]|[（(]?[0-9０-９一二三四五六七八九十]+[）)]|[①-⑳]|[ア-ン]\.)\s*")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
TABLE_RE = re.compile(r"^\s*\|")
FULLWIDTH_ALNUM_RE = re.compile(r"[Ａ-Ｚａ-ｚ０-９]{2,}")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿⬀-⯿\U0001F000-\U0001F2FF]")
BOLD_RE = re.compile(r"\*\*[^*\n]+\*\*")


@dataclasses.dataclass
class Finding:
    rule: str
    severity: str  # critical | warn | info
    line: int
    excerpt: str
    detail: str


# ---------------------------------------------------------------------------
# カタログ
# ---------------------------------------------------------------------------

# 常套句の最小集合（natural-japanese lint.py の FORBIDDEN_PHRASES から、業務文書で
# 誤検知しやすい「いかがでしょうか」「結論として」を info に落としたもの）
JA_PHRASES_WARN = [
    "と言えるでしょう", "と言えるだろう", "と言えます", "ということになるでしょう", "のではないでしょうか",
    "結論から言うと", "いかがでしたか", "まとめると", "総じて", "非常に重要", "極めて重要", "言うまでもなく",
    "言うまでもありません", "まさしく", "それでは、", "このような中", "ここで注目したいのは", "見ていきましょう",
    "紹介していきます", "解説していきます", "深掘りしていきます", "一概には言えません", "個人差がありますが",
    "あくまで一例ですが", "正面から扱う", "正面から見る", "正面から書く", "正面から立てる", "正面から回収する",
    "核心的", "鍵となる", "根本的な", "多角的", "包括的", "総合的", "掘り下げる", "深掘りする", "言語化する",
    "について見ていく", "を探求する", "大きく分けて3つ", "大きく分けて三つ",
]
JA_PHRASES_INFO = [
    "重要なのは", "このように", "不可欠", "ポイントは", "さて、", "大切なのは", "いかがでしょうか", "結論として",
    r"することができ(?:る|ます|た)", r"することが可能(?:です|だ|になる)", "という点で", r"という観点(?:から|で)",
    r"にとって(?:重要|不可欠)", "することによって", "であることは間違いない",
]
JA_STRONG = ["確実に", "必ず", "常に", "すべての", "完全に", "十分に", "万全", "問題ありません", "問題ございません",
             "圧倒的", "劇的"]
JA_PROCESS_WARN = ["AIとして", "AIである私", "としてお答え", "多角的に検証", "本回答では", "上記の通り確認",
                   "チェックを通過", "検証を経て", "検証済みのため", "確認済みのため"]
JA_PROCESS_INFO = ["確認済み", "検証済み", "チェック済み", "検証しました", "問題ないことを確認", "確認いたしました"]
JA_HEDGE_ENDINGS = ["かと存じます", "と思われます", "ではないでしょうか", "かもしれません", "と考えられます",
                    "可能性がございます", "可能性があります", "かと思います", "と思います"]
JA_CUSHIONS = ["恐れ入りますが", "お手数ですが", "お手数をおかけしますが", "大変恐縮ですが", "恐縮ですが",
               "申し訳ございませんが", "申し訳ありませんが", "差し支えなければ"]
JA_DOUBLE_KEIGO = ["おっしゃられ", "ご覧になられ", "拝見させていただ", "お伺いさせていただ", "お聞きになられ",
                   "お越しになられ", "ご利用になられ", "お読みになられ"]
JA_SASETE = ["ご確認させていただ", "ご提案させていただ", "ご連絡させていただ", "ご説明させていただ",
             "ご報告させていただ", "ご回答させていただ", "ご案内させていただ", "ご共有させていただ",
             "ご送付させていただ", "ご対応させていただ"]

DEKIRU_RE = re.compile(r"(?:できます|可能です|対応可能|利用可能|サポートされ|実現可能|設定可能|連携可能|取得可能)")
CONDITION_RE = re.compile(r"(?:ただし|条件|制約|場合|前提|要\b|必要|注意|制限|のみ|限り|除き|未対応|不可|要確認|"
                          r"エディション|リージョン|プレビュー|GA|以上|以下|以内|未満|→|※)")
# 幅・前提が要るのは見積り系の量（時間・割合・容量・金額）。件数・人数のような実測の個数は対象外。
NUMBER_UNIT_RE = re.compile(r"(?<![年月/\-.\d])\d+(?:[.,]\d+)?\s*(?:%|％|秒|分|時間|GB|TB|MB|KB|PB|円|倍|ms|ノード|クレジット)")
RANGE_RE = re.compile(r"(?:〜|～|程度|前後|約|以内|以上|以下|未満|場合|前提|条件|目安|最大|最小|上限|下限|想定|実測|"
                      r"実測値|要確認|推定|概算)")
UNVERIFIED_RE = re.compile(r"(?:未確認|確認できてお|確認できてい|明記されてい?な|明記なし|不明|把握できてい|確認が必要|"
                           r"検証が必要|要検証|わかりません|分かりません)")
LABEL_RE = re.compile(r"(?:【要確認】|要確認|【推定】|【未検証】|推奨)")


# ---------------------------------------------------------------------------
# 前処理
# ---------------------------------------------------------------------------

def _blank_keep_newlines(m: re.Match) -> str:
    return re.sub(r"[^\n]", " ", m.group(0))


def mask(text: str) -> str:
    """コードブロック・インラインコード・URL・HTMLコメント・front matter を空白化（行番号は保つ）。"""
    if text.startswith("---\n"):
        text = re.sub(r"(?s)\A---\n.*?\n---[^\n]*", _blank_keep_newlines, text, count=1)
    text = re.sub(r"(?s)```.*?```", _blank_keep_newlines, text)
    text = re.sub(r"`[^`\n]*`", _blank_keep_newlines, text)
    text = re.sub(r"(?s)<!--.*?-->", _blank_keep_newlines, text)
    text = re.sub(r"https?://\S+", _blank_keep_newlines, text)
    return text


@dataclasses.dataclass
class Doc:
    path: str
    text: str
    lines: list[str]
    sentences: list[tuple[int, str]]
    paragraphs: list[tuple[int, str]]
    chars: int

    def per_1000(self, n: int) -> float:
        return n * 1000 / max(self.chars, 1)

    def context(self, line_no: int) -> str:
        """その行と前後1行（条件が隣の行に書かれる箇条書き型に対応）。"""
        lo, hi = max(0, line_no - 2), min(len(self.lines), line_no + 1)
        return "\n".join(self.lines[lo:hi])


def build_doc(path: str, raw: str) -> Doc:
    text = mask(raw)
    lines = text.split("\n")
    sentences: list[tuple[int, str]] = []
    for i, line in enumerate(lines, 1):
        if TABLE_RE.match(line) or HEADING_RE.match(line):
            continue
        body = LIST_RE.sub("", line).strip()
        if not body:
            continue
        for s in SENT_SPLIT_RE.split(body):
            s = s.strip()
            if len(s) >= 2:
                sentences.append((i, s))
    paragraphs: list[tuple[int, str]] = []
    buf: list[str] = []
    start = 0
    for i, line in enumerate(lines, 1):
        if line.strip() and not HEADING_RE.match(line) and not TABLE_RE.match(line) and not LIST_RE.match(line):
            if not buf:
                start = i
            buf.append(line.strip())
        else:
            if buf:
                paragraphs.append((start, "".join(buf)))
                buf = []
    if buf:
        paragraphs.append((start, "".join(buf)))
    chars = len(re.sub(r"\s", "", text))
    return Doc(path, text, lines, sentences, paragraphs, chars)


def excerpt_of(line: str, limit: int = 60) -> str:
    s = line.strip()
    return s if len(s) <= limit else s[:limit] + "…"


def find_phrases(doc: Doc, patterns: list[str], rule: str, severity: str, detail: str,
                 max_reports: int = 40) -> list[Finding]:
    out: list[Finding] = []
    for pat in patterns:
        rx = re.compile(pat)
        for i, line in enumerate(doc.lines, 1):
            for m in rx.finditer(line):
                out.append(Finding(rule, severity, i, f"「{m.group(0)}」 {excerpt_of(line)}", detail))
                if len(out) >= max_reports:
                    return out
    return out


def count_matches(doc: Doc, patterns: list[str]) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for pat in patterns:
        rx = re.compile(pat)
        for i, line in enumerate(doc.lines, 1):
            for m in rx.finditer(line):
                hits.append((i, m.group(0)))
    return hits


def density_finding(doc: Doc, hits: list[tuple[int, str]], rule: str, info_at: float, warn_at: float,
                    detail: str, min_hits: int = 2) -> list[Finding]:
    d = doc.per_1000(len(hits))
    if len(hits) < min_hits or d < info_at:
        return []
    sev = "warn" if d >= warn_at else "info"
    sample = "、".join(f"L{l}「{w}」" for l, w in hits[:4])
    return [Finding(rule, sev, hits[0][0], sample, f"{len(hits)}件（{d:.1f}件/1000字）。{detail}")]


# ---------------------------------------------------------------------------
# 規則: 表現・工程・確信度
# ---------------------------------------------------------------------------

def rules_expression(doc: Doc) -> list[Finding]:
    f: list[Finding] = []
    f += find_phrases(doc, JA_PHRASES_WARN, "ai_phrase_ja", "warn",
                      "LLM常套句（natural-japanese forbidden-patterns.md 参照。lint.py が使える環境ではそちらを主とする）")
    f += find_phrases(doc, JA_PHRASES_INFO, "ai_phrase_ja", "info",
                      "頻度で効く常套句・翻訳調。1文書に数回なら自然", max_reports=25)
    f += find_phrases(doc, JA_STRONG, "strong_claim_ja", "info",
                      "強い語。対応する証拠（仕様・実測・一次情報）があるか Lane B が確認する")
    f += find_phrases(doc, JA_PROCESS_WARN, "process_narration", "warn",
                      "工程・自己言及の文。正文に入れてよいのは保証・観察・境界の3種だけ")
    f += find_phrases(doc, JA_PROCESS_INFO, "process_narration", "info",
                      "工程の記述なら削除。事実の報告なら何をどう確認したか（根拠）を添える。表の状態ラベルなら残す")
    f += density_finding(doc, count_matches(doc, JA_HEDGE_ENDINGS), "hedge_ending_ja", 3, 6,
                         "確信度を語尾で均している疑い。確認済みは断定、未確認は【要確認】、推定は根拠つきで")
    noms = count_matches(doc, [r"を(?:行|おこな)(?:う|い|っ|わ|え)", r"を実施(?:す|し)"])
    f += density_finding(doc, noms, "suru_nominalization_ja", 4, 8,
                         "「〜を行う」「〜を実施する」の名詞化。動詞で書く（分析を行う → 分析する）")
    conc = count_matches(doc, [r"(?:ですが|ますが|ものの|とはいえ|一方で|ながら)[^。\n]{0,40}(?:可能性|かもしれ|と思われ|かと存じ)"])
    if len(conc) >= 2:
        f.append(Finding("concessive_self_defense", "warn" if len(conc) >= 4 else "info", conc[0][0],
                         "、".join(f"L{l}" for l, _ in conc[:6]),
                         f"譲歩してからぼかす型が{len(conc)}件。結果＋境界＋未検証範囲の三要素に置換する"))
    return f


# ---------------------------------------------------------------------------
# 規則: 校准（制約のない「できる」・幅のない数値・標識のない未確認）
# ---------------------------------------------------------------------------

def rules_calibration(doc: Doc) -> list[Finding]:
    f: list[Finding] = []
    bare_dekiru = []
    for line_no, s in doc.sentences:
        if DEKIRU_RE.search(s) and not CONDITION_RE.search(doc.context(line_no)):
            bare_dekiru.append((line_no, s))
    if bare_dekiru:
        sev = "warn" if len(bare_dekiru) >= 3 else "info"
        sample = "、".join(f"L{l}" for l, _ in bare_dekiru[:6])
        f.append(Finding("dekiru_without_condition", sev, bare_dekiru[0][0], sample,
                         f"制約・条件が同じ文にも前後の行にもない「できる」が{len(bare_dekiru)}件。制約ゼロの『できる』は疑う（→ 設計上の含意まで書く）"))
    bare_num = []
    for line_no, s in doc.sentences:
        if NUMBER_UNIT_RE.search(s) and not RANGE_RE.search(doc.context(line_no)):
            bare_num.append((line_no, s))
    if bare_num:
        sample = "、".join(f"L{l}「{NUMBER_UNIT_RE.search(s).group(0)}」" for l, s in bare_num[:5])
        f.append(Finding("bare_number", "info", bare_num[0][0], sample,
                         f"幅・前提のない数値が{len(bare_num)}件。「元データがCSVの場合、20〜30%程度」の形にする"))
    unl = []
    for line_no, s in doc.sentences:
        if UNVERIFIED_RE.search(s) and not LABEL_RE.search(doc.context(line_no)):
            unl.append((line_no, s))
    for line_no, s in unl[:6]:
        f.append(Finding("unlabeled_unverified", "info", line_no, excerpt_of(s),
                         "未確認の内容に【要確認】の標識がない。確認方法（公式Doc／検証環境）もセットで書く"))
    return f


# ---------------------------------------------------------------------------
# 規則: 敬語・語域
# ---------------------------------------------------------------------------

def rules_register(doc: Doc, customer: bool) -> list[Finding]:
    f: list[Finding] = []
    sev = "warn" if customer else "info"
    f += find_phrases(doc, JA_DOUBLE_KEIGO, "double_keigo", sev, "二重敬語。ja-surface.md §3 の直しに従う")
    f += find_phrases(doc, JA_SASETE, "sasete_itadaku", "info",
                      "「ご〜させていただく」。相手の許可・恩恵がない場面は「〜いたします」「ご〜します」")
    sasete = count_matches(doc, ["させていただ"])
    if doc.per_1000(len(sasete)) > 3 and len(sasete) >= 2:
        f.append(Finding("sasete_itadaku_overuse", sev, sasete[0][0], f"{len(sasete)}件",
                         f"「させていただく」の密度 {doc.per_1000(len(sasete)):.1f}件/1000字。多くは「〜します」で足りる"))
    f += find_phrases(doc, [r"[一-鿿゠-ヿー]になります(?![か])"], "ni_narimasu", "info",
                      "名詞＋「になります」。「〜です」で足りる（変化を表す場合は残す）", max_reports=8)
    f += find_phrases(doc, [r"のほう[をはがにも]"], "no_hou", "info", "「〜のほう」は不要", max_reports=8)
    cush = count_matches(doc, JA_CUSHIONS)
    if len(cush) >= 3:
        f.append(Finding("cushion_overuse", sev, cush[0][0], "、".join(f"L{l}" for l, _ in cush[:5]),
                         f"クッション言葉が{len(cush)}件。一通に1回"))
    yoro = count_matches(doc, ["よろしくお願い"])
    if len(yoro) >= 2:
        f.append(Finding("closing_repeat", "info", yoro[0][0], f"{len(yoro)}件", "結びの定型は末尾に1回"))
    if customer:
        f += find_phrases(doc, ["御社"], "onsha_in_document", "info", "文書では「貴社」、会話では「御社」")
        if "ご査収" in doc.text and not re.search(r"添付|別添|同封", doc.text):
            line_no = next(i for i, l in enumerate(doc.lines, 1) if "ご査収" in l)
            f.append(Finding("gosashu_without_attachment", "info", line_no, "ご査収",
                             "添付・別添の言及がないのに「ご査収ください」"))
    return f


# ---------------------------------------------------------------------------
# 規則: 構造・装飾・字形
# ---------------------------------------------------------------------------

def rules_structure(doc: Doc) -> list[Finding]:
    f: list[Finding] = []
    reported = 0
    lengths = []
    for line_no, s in doc.sentences:
        n = len(s)
        if n >= 10:
            lengths.append(n)
        if n > 80 and reported < 10:
            f.append(Finding("long_sentence", "warn" if n > 120 else "info", line_no, excerpt_of(s),
                             f"{n}字。目安は50〜60字（公用文作成の考え方）。分割するか修飾を減らす"))
            reported += 1
    if len(lengths) >= 10:
        cv = statistics.pstdev(lengths) / statistics.mean(lengths)
        if cv < 0.28:
            f.append(Finding("uniform_sentence_length", "info", doc.sentences[0][0],
                             f"平均{statistics.mean(lengths):.0f}字、変動係数{cv:.2f}",
                             "文長が揃いすぎ。短い文と長い文を混ぜる（生成の癖）"))
    plens = [len(p) for _, p in doc.paragraphs if len(p) >= 20]
    if len(plens) >= 5:
        cv = statistics.pstdev(plens) / statistics.mean(plens)
        if cv < 0.25:
            f.append(Finding("uniform_paragraphs", "info", doc.paragraphs[0][0],
                             f"段落{len(plens)}本、変動係数{cv:.2f}",
                             "段落の厚みが均一。重要な節を厚く、軽い節を薄く"))
    nonblank = [l for l in doc.lines if l.strip()]
    bullets = [l for l in nonblank if LIST_RE.match(l)]
    if len(nonblank) >= 15 and len(bullets) / len(nonblank) >= 0.6:
        f.append(Finding("bullet_dominant", "info", 1, f"{len(bullets)}/{len(nonblank)}行が箇条書き",
                         "全篇が箇条書き。体裁スキル（customer-qa-style 等）がそれを規定するなら「残す/体裁上自然」"))
    bold_total = 0
    for start, p in doc.paragraphs:
        n = len(BOLD_RE.findall(p))
        bold_total += n
        if n > 1 and len([x for x in f if x.rule == "bold_per_paragraph"]) < 5:
            f.append(Finding("bold_per_paragraph", "info", start, f"太字{n}箇所", "太字は段落に核1箇所まで"))
    bold_total += sum(len(BOLD_RE.findall(l)) for l in doc.lines if LIST_RE.match(l))
    if bold_total > max(3, doc.chars / 150):
        f.append(Finding("bold_overuse", "warn", 1, f"太字{bold_total}箇所／{doc.chars}字", "強調が均等に散って効いていない"))
    emo = [(i, EMOJI_RE.findall(l)) for i, l in enumerate(doc.lines, 1) if EMOJI_RE.search(l)]
    for i, chars in emo[:5]:
        f.append(Finding("emoji", "info", i, "".join(chars[:5]), "絵文字は導航ラベル以外に使わない"))
    excl = [i for i, l in enumerate(doc.lines, 1) if re.search(r"(?<![\w/])[!！](?![\[(=])", l)]
    if excl:
        f.append(Finding("exclamation", "info", excl[0], f"{len(excl)}行", "業務文書に感嘆符は使わない"))
    return f


def rules_typography(doc: Doc) -> list[Finding]:
    f: list[Finding] = []
    fw = count_matches(doc, [FULLWIDTH_ALNUM_RE.pattern])
    if fw:
        f.append(Finding("fullwidth_alnum", "info", fw[0][0], "、".join(w for _, w in fw[:5]), "全角英数は半角に"))
    f += find_phrases(doc, [r"(?<=[一-鿿぀-ヿ])[,;?!](?=\s*[一-鿿぀-ヿ]|\s*$)",
                            r"(?<=[一-鿿぀-ヿ])\.(?=\s*[一-鿿぀-ヿ]|\s*$)"],
                      "halfwidth_punct", "info", "日本語の中に半角句読点。「、」「。」に統一", max_reports=10)
    zp = count_matches(doc, ["，", "；", "“", "”"])
    if zp:
        f.append(Finding("nonstandard_punct", "info", zp[0][0], "".join(sorted({w for _, w in zp})),
                         f"「，」「；」「“”」が{len(zp)}件。「、」「。」「」に統一（公用文流儀で「，」を使う場合は残す）"))
    bad: dict[str, int] = {}
    for i, line in enumerate(doc.lines, 1):
        for ch in HAN_RE.findall(line):
            if ch in bad:
                continue
            try:
                ch.encode("cp932")
            except UnicodeEncodeError:
                bad[ch] = i
    if bad:
        f.append(Finding("non_jis_kanji", "warn", min(bad.values()), "".join(sorted(bad, key=bad.get)),
                         f"cp932 に無い漢字が{len(bad)}種。簡体字の混入か JIS外の異体字。日本語の字形に直す（ja-surface.md §4）"))
    tildes = {w for _, w in count_matches(doc, [r"(?<=\d)[〜～~](?=\d)"])}
    if len(tildes) >= 2:
        f.append(Finding("range_symbol_mixed", "info", 1, "".join(sorted(tildes)), "範囲記号が混在。「〜」に統一"))
    return f


# ---------------------------------------------------------------------------
# 実行
# ---------------------------------------------------------------------------

SEV_ORDER = {"critical": 0, "warn": 1, "info": 2}


def lint_text(path: str, raw: str, customer: bool = False) -> dict:
    doc = build_doc(path, raw)
    findings = (rules_expression(doc) + rules_calibration(doc) + rules_register(doc, customer)
                + rules_structure(doc) + rules_typography(doc))
    findings.sort(key=lambda x: (SEV_ORDER[x.severity], x.line))
    counts = {k: sum(1 for x in findings if x.severity == k) for k in SEV_ORDER}
    penalty = (counts["critical"] * 8 + counts["warn"] * 4 + counts["info"] * 0.5) * (1000 / max(doc.chars, 1000))
    return {
        "file": path,
        "chars": doc.chars,
        "sentences": len(doc.sentences),
        "customer": customer,
        "summary": {**counts,
                    "density_per_1000": round(doc.per_1000(len(findings)), 2),
                    "score_hint": round(max(100 - penalty, 20), 1)},
        "findings": [dataclasses.asdict(x) for x in findings],
    }


def finding_key(x: dict) -> tuple:
    """baseline 比較用のキー。語句ヒットは (rule, 語句)、集計系は (rule, severity)、
    それ以外は (rule, excerpt 先頭40字)。行の文面が変わっても同じ疑いは同じキーになる。"""
    ex = x["excerpt"]
    if ex.startswith("「") and "」" in ex:
        return (x["rule"], ex[1:ex.index("」")])
    if re.match(r"^\d+件", ex) or "変動係数" in ex or "／" in ex or "=" in ex or ex.startswith("L"):
        return (x["rule"], x["severity"])
    return (x["rule"], ex[:40])


def diff_baseline(result: dict, baseline_path: str) -> dict | None:
    try:
        base = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
        prev: dict[tuple, int] = {}
        for x in base.get("findings", []):
            k = finding_key(x)
            prev[k] = prev.get(k, 0) + 1
    except (OSError, ValueError, KeyError, TypeError):
        print(f"warning: --baseline {baseline_path} を読めないので差分を省略します", file=sys.stderr)
        return None
    new, persisting = [], []
    remaining = dict(prev)
    for x in result["findings"]:
        k = finding_key(x)
        if remaining.get(k, 0) > 0:
            remaining[k] -= 1
            persisting.append(x)
        else:
            new.append(x)
    resolved = sorted(f"{k[0]}: {k[1]}" for k, n in remaining.items() for _ in range(n))
    return {"resolved": resolved, "new": new, "persisting": persisting}


def render_text(result: dict, diff: dict | None) -> str:
    s = result["summary"]
    out = [f"{result['file']}  chars={result['chars']}  sentences={result['sentences']}  customer={result['customer']}",
           f"critical={s['critical']} warn={s['warn']} info={s['info']}  density={s['density_per_1000']}/1000字  score_hint={s['score_hint']}（目安。判断は台帳で）",
           ""]
    for sev in ("critical", "warn", "info"):
        items = [x for x in result["findings"] if x["severity"] == sev]
        if not items:
            continue
        out.append(f"## {sev} ({len(items)})")
        for x in items:
            out.append(f"- L{x['line']} {x['rule']}: {x['excerpt']}\n    → {x['detail']}")
        out.append("")
    if diff:
        out.append(f"## baseline 差分: resolved={len(diff['resolved'])} new={len(diff['new'])} persisting={len(diff['persisting'])}")
        for x in diff["new"]:
            out.append(f"- NEW L{x['line']} {x['rule']}: {x['excerpt']}")
    return "\n".join(out)


def run_hook() -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    path = (data.get("tool_input") or {}).get("file_path") or ""
    if not path.endswith(".md") or not Path(path).is_file():
        return 0
    result = lint_text(path, Path(path).read_text(encoding="utf-8", errors="replace"))
    s = result["summary"]
    if s["critical"] + s["warn"] == 0:
        return 0
    top = [x for x in result["findings"] if x["severity"] != "info"][:8]
    msg = [f"ja_lint: {path} に warn 以上が {s['critical'] + s['warn']} 件。判断台帳に載せて直す/残すを決めること。"]
    msg += [f"- L{x['line']} {x['rule']}: {x['excerpt']} → {x['detail']}" for x in top]
    print("\n".join(msg), file=sys.stderr)
    return 2


def main() -> int:
    ap = argparse.ArgumentParser(description="日本語の成果物を決定的に検査する")
    ap.add_argument("file", nargs="?", help="対象ファイル（Markdown／テキスト）")
    ap.add_argument("--json", action="store_true", help="JSON で出力")
    ap.add_argument("--baseline", help="前回の --json 出力。resolved/new/persisting を仕分ける")
    ap.add_argument("--customer", action="store_true", help="顧客向け文書として敬語・語域の severity を上げる")
    ap.add_argument("--hook", action="store_true", help="Claude Code PostToolUse フックとして動く")
    args = ap.parse_args()
    if args.hook:
        return run_hook()
    if not args.file:
        ap.error("file を指定してください")
    p = Path(args.file)
    if not p.is_file():
        print(f"error: {args.file} が見つからないかファイルではありません", file=sys.stderr)
        return 1
    raw = p.read_text(encoding="utf-8", errors="replace")
    if len(re.sub(r"\s", "", raw)) < 50:
        print("error: 本文が短すぎます（50字未満）", file=sys.stderr)
        return 1
    result = lint_text(str(p), raw, args.customer)
    diff = diff_baseline(result, args.baseline) if args.baseline else None
    if diff:
        result["baseline_diff"] = diff
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result, diff))
    return 0


if __name__ == "__main__":
    sys.exit(main())
