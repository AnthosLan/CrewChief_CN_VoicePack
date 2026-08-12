"""
Post-process a machine-translated inventory: normalise numerals, then apply manual overrides.

Two passes, deliberately separate:

  1. Numerals. The model leaves Arabic digits in perfectly good Chinese ('第17名', '2号弯').
     Deterministic to fix, so it is code rather than 1452 hand edits. XTTS's Chinese frontend
     is not guaranteed to read a bare digit, and a folder that plays silence is worse than one
     that plays an awkward phrase.

  2. Overrides from a corrections CSV. Everything the model got semantically wrong -- these
     cannot be derived, so they are data, reviewed by a human and versioned in this repo.
     Keyed on original_english so a re-translation with a better prompt keeps the corrections.

Usage:
    python3 scripts/fix_translation.py \
        --in translations/chief_wave1_zh.csv \
        --corrections translations/chief_wave1_corrections.csv \
        --out translations/chief_wave1_final.csv
    python3 scripts/fix_translation.py --in ... --report_numerals   # 只列出会改哪些，不写文件
"""

import argparse
import csv
import os
import re
import sys

DIGITS = "零一二三四五六七八九"

# Wording the model varies between runs even at temperature 0.2, where every variant means the
# same thing. Hearing '一号分段' and '第一分段' in the same race sounds like two different chiefs,
# so they are collapsed here rather than in ~100 near-identical correction rows.
#
# Applied before the manual overrides, so a correction row always wins over a rule here.
TERM_FIXES = [
    # '一号分段' / '二号段' -> '第一分段'. CrewChief itself has no preference; consistency is ours.
    (r'([一二三])号分段', r'第\1分段'),
    (r'第([一二三])段(?!位)', r'第\1分段'),
    (r'([一二三])号和([一二三])号分段', r'第\1和第\2分段'),
    # A radio call says 零点一秒, not the textbook 十分之一秒. '几十分之一秒' is worse still --
    # it reads as one part in several dozen rather than a few tenths.
    (r'几十分之一秒', '零点几秒'),
    (r'十分之一秒', '零点一秒'),
    (r'十分之二秒', '零点二秒'),
    (r'十分之三秒', '零点三秒'),
    # 'off the pace' is the benchmark lap, not a vague notion of rhythm.
    (r'比当前节奏慢', '比最快慢'),
    (r'比节奏慢', '比最快慢'),
    (r'比标杆慢', '比最快慢'),
    (r'比最佳圈速慢', '比最快慢'),
    (r'落后节奏', '比最快慢'),
    (r'落后领跑者节奏', '比领跑的慢'),
    # The model alternates between these for 'fastest'/'purple'.
    (r'都是全场最快', '全都是全场最快'),
    # 'spotter' came back eight different ways across the acknowledge category alone. 报站 is the
    # worst of them -- it is what a bus does when it announces the next stop. 领航员 is wrong in a
    # different way: that is the rally codriver, a role CrewChief models separately.
    # Longest first, so 赛车观察员 is not left as 赛车 + 观察员.
    (r'赛车手助理|赛车联络员|无线电报员|赛车报员|空中观察员|赛车观察员|领航员', '观察员'),
    (r'(不再|不)(进行)?位置报告', r'\1报点'),
    (r'报站', '报点'),
    (r'呼叫', '报点'),
    # 'left side tyres' came back as 左侧行胎 / 左侧行驶侧轮胎 -- 'side' got read as 行驶.
    (r'([左右])侧行驶侧轮胎', r'\1侧轮胎'),
    (r'([左右])侧行胎', r'\1侧胎'),
    (r'([左右])侧行驶轮胎', r'\1侧轮胎'),
    # A single row came back in traditional characters.
    (r'左側輪胎', '左侧轮胎'),
    (r'右側輪胎', '右侧轮胎'),
    # A space between a Latin token and Chinese makes XTTS break there, and it often swallows
    # what follows: 'DRS 不再可用' came out at 0.49s, shorter than the four Han characters alone
    # would take. 'GT4 车' truncated to 0.22s the same way. Closing the gap fixes both.
    (r'([A-Za-z0-9]) +([一-鿿])', r'\1\2'),
    (r'([一-鿿]) +([A-Za-z0-9])', r'\1\2'),
]


def to_chinese_number(n):
    """
    0-99 only, which covers every numeral CrewChief puts in a phrase (positions, corners,
    gallons, minutes). Reads the way a person would: 17 -> 十七, not 一十七.
    """
    n = int(n)
    if n < 10:
        return DIGITS[n]
    if n < 20:
        return "十" + (DIGITS[n % 10] if n % 10 else "")
    tens, units = divmod(n, 10)
    return DIGITS[tens] + "十" + (DIGITS[units] if units else "")


def normalise_numerals(text):
    """
    Convert standalone Arabic numerals to Chinese. Leaves DRS/KERS-style tokens alone because
    they are kept in English on purpose (see translations/glossary_zh.txt).
    """
    # 'P17' -> '第十七名'. The model converts most of these itself but not all, and the ones
    # it misses would otherwise be read out letter by letter.
    text = re.sub(r'\bP(\d{1,2})\b', lambda m: "第" + to_chinese_number(m.group(1)) + "名", text)
    # Any remaining 1-2 digit run that is not part of an alphanumeric identifier. The digit
    # lookbehind matters: without it 'GT300' matched its trailing '00' and became 'GT3零',
    # quietly renaming a car class.
    text = re.sub(r'(?<![A-Za-z\d])(\d{1,2})(?![A-Za-z\d])',
                  lambda m: to_chinese_number(m.group(1)), text)
    return text


def load_corrections(paths):
    """
    Merge one or more correction CSVs. Later files win, so pass this wave's file last.

    Feeding earlier waves' files in keeps a phrase that appears in several waves translated the
    same way -- otherwise wave 3 quietly reverts to whatever the model produced and 空力 becomes
    空气动力套件 again.
    """
    if not paths:
        return {}
    if isinstance(paths, str):
        paths = [paths]
    out, own = {}, set()
    for i, path in enumerate(paths):
        if not os.path.exists(path):
            continue
        loaded = _load_one(path)
        out.update(loaded)
        # Only the last file is "this wave's" -- inherited files legitimately carry rows that
        # match nothing here, and warning about all of them buries the ones that matter.
        own = set(loaded) if i == len(paths) - 1 else own
    return out, own


def _load_one(path):
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            # '#' rows group the corrections by category for whoever reviews them next.
            # They must not become corrections themselves, and a comment containing an ASCII
            # comma would parse as a perfectly valid two-field row.
            if row and row[0].lstrip().startswith("#"):
                continue
            if not row or not row[0].strip():
                continue
            # An English phrase containing a comma must be quoted. Unquoted, csv splits it and
            # field 1 becomes the tail of the ENGLISH rather than the Chinese -- which then gets
            # written into the pack as if it were a translation. Refuse to guess.
            if len(row) != 2:
                raise SystemExit(
                    "修正表第 %d 行有 %d 个字段，应为 2 个。含逗号的英文必须加引号：\n    %s"
                    % (reader.line_num, len(row), ",".join(row))
                )
            if row[1].strip():
                out[row[0].strip()] = row[1].strip()
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", required=True)
    parser.add_argument("--corrections", default=None, nargs="*",
                        help="修正表，可传多个。后面的覆盖前面的，所以把本波的放最后。"
                             "传入前几波的修正表可以让同一句英文在各波保持同一译法。")
    parser.add_argument("--out", default=None)
    parser.add_argument("--report_numerals", action="store_true",
                        help="只打印数字归一化会改动的行，不写输出文件")
    args = parser.parse_args()

    with open(args.infile, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]

    corrections, own_keys = load_corrections(args.corrections)
    applied, numeral_changes, unused = set(), [], set(own_keys)

    term_changes = 0
    for row in body:
        english, chinese = row[4], row[2]
        normalised = chinese
        for pattern, replacement in TERM_FIXES:
            normalised = re.sub(pattern, replacement, normalised)
        if normalised != chinese:
            term_changes += 1
        chinese = normalised
        # A hand-written correction is the last word: it replaces the normalised text outright
        # rather than being normalised in turn, so a reviewer can always override a rule.
        if english in corrections:
            chinese = corrections[english]
            applied.add(english)
            unused.discard(english)
        fixed = normalise_numerals(chinese)
        if fixed != chinese:
            numeral_changes.append((chinese, fixed))
        # subtitle and text_for_tts stay in lockstep; the pack shows what it says.
        row[2] = row[3] = fixed

    if args.report_numerals:
        seen = set()
        for before, after in numeral_changes:
            if before in seen:
                continue
            seen.add(before)
            print("  %-42s -> %s" % (before, after))
        print("\n共 %d 行会改，去重后 %d 种" % (len(numeral_changes), len(seen)))
        return

    if not args.out:
        sys.exit("需要 --out（或用 --report_numerals 只看不写）")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(body)

    print("%d 行 -> %s" % (len(body), args.out))
    print("  术语归一化 %d 行" % term_changes)
    print("  数字归一化 %d 行" % len(numeral_changes))
    print("  人工修正   %d 条生效（其中本波 %d 条）" % (len(applied), len(applied & own_keys)))
    if unused:
        # A correction that matches nothing means the English drifted -- silently ignoring it
        # would let the fix quietly stop applying on the next re-translation.
        print("\n⚠️  这些修正没有匹配到任何行，检查 original_english 是否写错：")
        for english in sorted(unused):
            print("    " + english)


if __name__ == "__main__":
    main()
