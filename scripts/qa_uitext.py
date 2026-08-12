"""
Check translated UI strings before they ship. Exits 1 if anything is wrong.

This is to the UI what qa_pack.py is to the audio: the failures it catches are the ones nobody
notices by looking. The wrap check is the reason the script exists at all --

    Utilities.cs:672  NewlinesInLongString
        int splitIndex = _line.Substring(0, maxLength).LastIndexOf(" ");
        if (splitIndex == -1) splitIndex = maxLength;   // no space -- hard cut
        result += _line.Substring(0, splitIndex) + NewLine;
        _line = _line.Substring(splitIndex + 1);        // skips the char at splitIndex

English wraps on a space and the skipped character is that space. Chinese has no spaces, so the
cut lands mid-text and the skipped character is a Han character. One character is lost per wrap,
silently: the sentence still renders, it just reads slightly wrong. The fix is to insert explicit
'\' breaks (a marker en.txt already uses) so no segment ever reaches the limit.

Usage:
    python3 scripts/qa_uitext.py --csv translations/ui_wave1_final.csv
    python3 scripts/qa_uitext.py --txt src/ui_text_zh.txt
"""

import argparse
import csv
import os
import re
import sys

DEFAULT_EN = os.path.expanduser("~/Projects/CrewChiefV4-main/CrewChiefV4/ui_text/en.txt")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_uitext_inventory import parse_en, is_invariant, wrap_limit  # noqa: E402

CJK = re.compile(r"[一-鿿]")
PLACEHOLDER = re.compile(r"\{\d+\}")
MNEMONIC = re.compile(r"&([A-Za-z0-9])")


def check(key, zh, english, errors, warnings):
    limit = wrap_limit(key)
    if limit:
        for segment in zh.split("\\"):
            if len(segment) > limit:
                errors.append(
                    "%s: 折行会吞字——有一段 %d 字，超过 %d。用 \\ 手工断开\n      %s"
                    % (key, len(segment), limit, segment[:60] + ("…" if len(segment) > 60 else ""))
                )

    # Configuration.merge() does line.Split('=')[1], so everything after a second '=' is dropped.
    # Two English help strings are already truncated this way upstream; no reason to add more.
    if "=" in zh:
        errors.append("%s: 值里有 '='，CrewChief 会从那里截断。改用「等于」或冒号" % key)

    if "\n" in zh or "\r" in zh or "\t" in zh:
        errors.append("%s: 值里有换行或制表符，只能用 \\ 表示换行" % key)

    # '&S' makes Alt+S activate the control. Dropping it silently removes the keyboard shortcut.
    if MNEMONIC.search(english) and not MNEMONIC.search(zh):
        errors.append("%s: 英文有 &X 快捷键标记，中文丢了。中文习惯写成「停止(&S)」" % key)

    # A dropped {0} does not throw -- String.Format just renders a sentence with a hole in it.
    if set(PLACEHOLDER.findall(english)) != set(PLACEHOLDER.findall(zh)):
        errors.append("%s: 占位符对不上，英文 %s，中文 %s"
                      % (key, PLACEHOLDER.findall(english) or "无", PLACEHOLDER.findall(zh) or "无"))

    if not CJK.search(zh):
        # Legitimate for a handful of keys (game names, 'PoV'), so it is a warning, not an error.
        warnings.append("%s: 没有汉字，确认是有意保留英文——%s" % (key, zh[:50]))


def load_csv(paths):
    rows = []
    for path in paths:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) != 4:
                    sys.exit("%s 有 %d 个字段的行，应为 4 个：\n    %s"
                             % (path, len(row), ",".join(row)))
                _section, key, zh, english = row
                if zh.strip():
                    rows.append((key, zh.strip(), english.strip()))
    return rows


def load_txt(path, en_values):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("#") or "=" not in line:
                continue
            key, zh = line.split("=", 1)
            key, zh = key.strip(), zh.strip()
            if zh:
                rows.append((key, zh, en_values.get(key, "")))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", nargs="*", default=[])
    parser.add_argument("--txt", nargs="*", default=[])
    parser.add_argument("--en", default=DEFAULT_EN)
    args = parser.parse_args()

    if not args.csv and not args.txt:
        sys.exit("需要 --csv 或 --txt")

    en_rows = parse_en(args.en)
    en_values = {key: value for _s, key, value in en_rows}

    rows = load_csv(args.csv)
    for path in args.txt:
        rows += load_txt(path, en_values)

    errors, warnings = [], []
    seen = {}
    for key, zh, english in rows:
        if key not in en_values:
            # A typo'd key is not an error CrewChief reports -- getUIString just returns the key
            # name and the label reads 'enable_spoter'.
            errors.append("%s: en.txt 里没有这个 key，检查拼写" % key)
            continue
        if is_invariant(key):
            # These parse as enums. A translated value does not crash -- it stops matching, and
            # the property quietly leaves its category or its game filter.
            errors.append("%s: 这是标识符不是显示文本，必须保持英文原样（现在是 %s）" % (key, zh[:30]))
            continue
        if key in seen and seen[key] != zh:
            errors.append("%s: 出现两次且译文不同：%s / %s" % (key, seen[key][:30], zh[:30]))
        seen[key] = zh
        check(key, zh, english or en_values[key], errors, warnings)

    # Two different English strings landing on the same Chinese is how a settings list loses a
    # row: 'R3E launch exe' and 'LMU launch exe' both came back as 启动程序, and 'rF1 install
    # path' / 'rF2 install path' both as rFactor 安装路径. The user then has two identical-looking
    # settings and no way to tell which game each belongs to. Some collisions are fine
    # (singular/plural of the same sentence), so this is a warning.
    by_translation = {}
    for key, zh, english in rows:
        if key in en_values and not is_invariant(key):
            by_translation.setdefault(zh, set()).add(en_values[key])
    for zh, englishes in sorted(by_translation.items()):
        if len(englishes) > 1:
            warnings.append("译文重复——%d 句不同的英文都译成了「%s」：\n        %s"
                            % (len(englishes), zh, "\n        ".join(sorted(englishes))))

    print("检查 %d 条译文（en.txt 共 %d 条）" % (len(rows), len(en_values)))
    if warnings:
        print("\n提示 %d 条：" % len(warnings))
        for w in warnings:
            print("  · " + w)
    if errors:
        print("\n异常 %d 条：" % len(errors))
        for e in errors:
            print("  ✗ " + e)
        sys.exit(1)
    print("异常 0 条")


if __name__ == "__main__":
    main()
