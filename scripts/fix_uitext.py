"""
Post-process translated UI strings: normalise wording, apply manual overrides, insert line breaks.

Same shape as fix_translation.py, and it reuses that module's corrections loader so the review
file format is identical across audio and UI work. Two differences:

The third pass is different. fix_translation.py normalises numerals; this one inserts '\' breaks
into the long-form strings so CrewChief never wraps them itself (see insert_breaks).

And two of fix_translation.py's rules are deliberately NOT carried over:

  - fix_translation.py converts Arabic numerals to Chinese words, because XTTS has to pronounce
    them. Here the opposite is true -- '0 to disable' and 'Set to 5' are values the user types
    into a settings box, and spelling them out would be wrong.

  - fix_translation.py strips spaces between Latin and Han characters, because XTTS breaks the
    sentence there and swallows the rest. On screen that space is correct Chinese typography
    ('UDP 端口'), so it is left alone.

Usage:
    python3 scripts/fix_uitext.py --in translations/ui_wave1_zh.csv \
        --corrections translations/ui_wave1_corrections.csv \
        --out translations/ui_wave1_final.csv
"""

import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fix_translation import load_corrections  # noqa: E402
from make_uitext_inventory import wrap_limit  # noqa: E402

# Where a forced line break may go, best first. Splitting on punctuation reads like a deliberate
# line break; splitting mid-word reads like the bug we are avoiding.
BREAK_POINTS = "。！？；，、）】」"

# Characters that must never be split across a line break. Chinese can wrap between any two
# characters, but 'Steam app ID' and 'trackLandmarksData.json' cannot -- the first pass produced
# 'Steam a\pp ID' and 'trackLandmar\ksData.json' in 14 rows.
TOKEN_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._/-"

# Wording the model varies between rows where every variant means the same thing. Collapsed here
# rather than in near-identical correction rows. Applied before the manual overrides, so a
# correction always wins over a rule.
TERM_FIXES = [
    # A real newline is the model's attempt at the '\' line-break marker, but written literally it
    # would break the key = value format of the generated txt. Runs first so insert_breaks sees
    # the segments the author intended.
    (r"[\r\n\t]+", "\\\\"),
    # The model alternates between these for the same English word, and a settings screen that
    # says 启用 on one row and 开启 on the next reads like two different translators.
    (r"开启", "启用"),
    (r"关闭时", "禁用时"),
    # 'Sound Pack' slipped through as 声音包 in early runs even with the glossary.
    (r"声音包", "语音包"),
    (r"音效包", "语音包"),
    # 'driver names' -- 车手名 is the term used throughout the voice pack docs.
    (r"驾驶员名称|驾驶员姓名|车手姓名", "车手名"),
    (r"个性化设置(?!项)", "个性化称呼"),
    # Product name. 'crew chief' the role is 车队工程师, but in the UI it is always the app,
    # and en.txt spells it with a space.
    (r"车队工程师\s*-\s*", "Crew Chief - "),
    (r"CrewChief", "Crew Chief"),
    # 'devs' came back as both across neighbouring menu items.
    (r"开发人员", "开发者"),
    # 'new sounds' is the voice pack being reloaded, so keep it in the same vocabulary.
    (r"新声音", "新语音"),
    (r"声音文件", "语音文件"),
    (r"日志类型 - 声音", "日志类型 - 语音"),
    # 'warnings' came back as both, sometimes on adjacent rows (刹车抱死提醒 / 打滑警告阈值).
    (r"警告", "提醒"),
    # FCY (full course yellow) got three readings in four adjacent rows: 赛事控制员 / 赛事控制 /
    # 赛事黄旗, plus 虚拟安全车 elsewhere. The voice pack calls it 全场黄旗.
    (r"赛事控制员|赛事控制(?!室)|赛事黄旗|虚拟安全车", "全场黄旗"),
    (r"\bFCY\b", "全场黄旗"),
    # 'pit state messages' -- 播报 everywhere else in the pack.
    (r"进站消息", "进站播报"),
    # 'Wrong Way' and single quotes around a game string.
    (r"错向行驶|错误方向", "逆向行驶"),
    (r"'([^']*)'", r"「\1」"),
    # 'verbose' as a log level is 详细, not 详细程度.
    (r"日志类型 - 详细程度", "日志类型 - 详细"),
    # 'the Chief' is the race engineer. 首席 on its own is a job-title fragment, not a person.
    (r"首席(?!执行)", "工程师"),
    # The CrewChief author's name. Proper names stay in English, same rule as the voice pack.
    (r"贝尔沃斯基先生|贝洛斯基先生|贝罗斯基先生", "Mr Belowski"),
    # 'App' -- 程序 throughout; 应用程序 turned up in 24 rows next to 应用 in others.
    # Deliberately NOT a blanket 应用 -> 程序: that also rewrote 'Steam 应用 ID', and the break
    # inserter then split the result as 'Steam 程\序 ID'.
    (r"应用程序", "程序"),
    # 'Steam app ID' is a Steam term the glossary keeps in English; the model rendered it three
    # different ways across 24 near-identical rows.
    (r"Steam ?(应用|程序) ?ID", "Steam app ID"),
    (r"Notepad", "记事本"),
    # 'messages' is 播报 in this pack; 播报消息 doubles up and 提醒消息 does the same.
    (r"播报消息", "播报"),
    (r"提醒消息", "提醒"),
    # Must match the button label itself (U1's toggle_button), or the help text names a control
    # the user cannot find.
    (r"按住并释放按钮", "按下并松开按钮"),
    # A space between Latin and Han is correct Chinese typography and the model applies it only
    # about half the time ('复制 CrewChief 设置' next to '与CrewChief对话'). Note this is the
    # OPPOSITE of fix_translation.py, which strips these spaces because XTTS breaks on them --
    # nothing is being spoken here.
    (r"([一-鿿])([A-Za-z0-9])", r"\1 \2"),
    (r"([A-Za-z0-9])([一-鿿])", r"\1 \2"),
    # Chinese UI convention: a label ending in a colon uses the full-width form.
    (r":$", "："),
    # The mnemonic is appended after translation, so on a label ending in a colon it lands after
    # it -- '游戏过滤：(&G)'. The colon separates the label from its input box and has to stay last.
    (r"：(\(&[A-Za-z0-9]\))$", r"\1："),
    # 'X - for Y' rows: 适用于 in most, 用于 / 为 in a few, and one em-dash where the rest use '-'.
    (r"^([A-Za-z0-9]+) *(?:-|——|—) *(?:用于|为)", r"\1 - 适用于"),
    (r"^([A-Za-z0-9]+) *(?:——|—) *适用于", r"\1 - 适用于"),
    # SteamVR overlay axis controls: 增加 X 旋转 next to 增加 Y 轴旋转 in the same list.
    (r"(增加|减少)\s*([XYZ])\s*旋转", r"\1 \2 轴旋转"),
    (r"([XYZ])\s*旋转增量", r"增加 \1 轴旋转"),
    # Full-width brackets already carry the separation, so the space the Latin rule added
    # around them is redundant. Runs last, after that rule.
    (r"([「（])\s+", r"\1"),
    (r"\s+([」）])", r"\1"),
    (r"([」）])\s+([一-鿿])", r"\1\2"),
    (r"([一-鿿])\s+([「（])", r"\1\2"),
    # A space between two Han characters is never right, and the rules above can leave one behind
    # when a Latin token is replaced by Chinese ('FCY 维修道' -> '全场黄旗 维修道').
    (r"([一-鿿]) +([一-鿿])", r"\1\2"),
]


def insert_breaks(text, limit):
    """
    Insert '\\' so no segment reaches `limit` characters.

    Done in code rather than by asking the model, for the same reason mnemonics are: a 14B model
    cannot reliably count to 44. CrewChief would otherwise wrap the text itself and drop one Han
    character at every boundary (Utilities.cs:672 -- see qa_uitext.py).

    Breaks are placed at the last punctuation mark that fits, so the result reads like a chosen
    line break. Only if a segment has no punctuation at all does it get cut at the limit, which is
    still correct -- the break is explicit, so nothing is skipped.
    """
    out = []
    for segment in text.split("\\"):
        while len(segment) > limit:
            window = segment[:limit]
            cut = max((window.rfind(p) for p in BREAK_POINTS), default=-1)
            # +1 so the punctuation ends the line rather than starting the next one. A break at
            # position 0 would make no progress, so fall back to a hard cut.
            cut = cut + 1 if cut > 0 else limit
            if (cut < len(segment)
                    and segment[cut - 1] in TOKEN_CHARS and segment[cut] in TOKEN_CHARS):
                # The cut landed inside 'Steam app ID' or a filename. Back off to where that run
                # started; if the run is what makes the line too long there is nowhere better to
                # go, so keep the hard cut rather than looping forever.
                back = cut
                while back > 0 and segment[back - 1] in TOKEN_CHARS:
                    back -= 1
                if back > 0:
                    cut = back
            out.append(segment[:cut].rstrip())
            # The space that used to separate the two tokens has become the line break itself.
            segment = segment[cut:].lstrip()
        out.append(segment)
    return "\\".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", required=True)
    parser.add_argument("--corrections", default=None, nargs="*",
                        help="修正表，可传多个。后面的覆盖前面的，所以把本波的放最后。")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(args.infile, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]

    corrections, own_keys = load_corrections(args.corrections)
    applied, unused = set(), set(own_keys)
    term_changes = 0
    break_changes = 0
    missing = 0

    for row in body:
        if len(row) != 4:
            sys.exit("%s 有 %d 个字段的行，应为 4 个：\n    %s"
                     % (args.infile, len(row), ",".join(row)))
        english, chinese = row[3], row[2]
        normalised = chinese
        for pattern, replacement in TERM_FIXES:
            normalised = re.sub(pattern, replacement, normalised)
        if normalised != chinese:
            term_changes += 1
        chinese = normalised
        if english in corrections:
            chinese = corrections[english]
            applied.add(english)
            unused.discard(english)
        # Last, so a reviewer's hand-placed breaks are respected and only over-long runs between
        # them get split further.
        limit = wrap_limit(row[1])
        if limit and chinese.strip():
            wrapped = insert_breaks(chinese, limit)
            # This whole script exists because CrewChief drops a character when it wraps. Dropping
            # one here instead would be the same bug wearing a different hat, so check rather than
            # trust: only whitespace and the markers themselves may differ.
            if re.sub(r"[\s\\]", "", wrapped) != re.sub(r"[\s\\]", "", chinese):
                sys.exit("%s: 插入换行符时丢了字符，这是 bug\n  原文 %s\n  结果 %s"
                         % (row[1], chinese, wrapped))
            if wrapped != chinese:
                break_changes += 1
            chinese = wrapped
        if not chinese.strip():
            missing += 1
        row[2] = chinese

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(body)

    print("%d 行 -> %s" % (len(body), args.out))
    print("  术语归一化 %d 行" % term_changes)
    print("  插入换行符 %d 行" % break_changes)
    print("  人工修正   %d 条生效（其中本波 %d 条）" % (len(applied), len(applied & own_keys)))
    if missing:
        print("  ⚠️  %d 行没有译文" % missing)
    if unused:
        # A correction that matches nothing means the English drifted -- silently ignoring it
        # would let the fix quietly stop applying on the next re-translation.
        print("\n⚠️  这些修正没有匹配到任何行，检查 original_english 是否写错：")
        for english in sorted(unused):
            print("    " + english)


if __name__ == "__main__":
    main()
