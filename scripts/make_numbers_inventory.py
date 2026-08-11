"""
Generate translations/numbers_zh.csv -- the sound folder inventory for the Chinese number reader.

Also mirrors NumberReaderZh.cs in Python (--verify) so the folder sequences can be checked on a Mac,
where the C# can't be compiled. If you change one, change the other; --verify is what catches drift.

Usage:
    python3 scripts/make_numbers_inventory.py --out translations/numbers_zh.csv
    python3 scripts/make_numbers_inventory.py --verify
"""

import argparse
import csv
import os
import sys

DIGITS = "零一二三四五六七八九"

# Place-value and unit words. Folder name -> spoken Chinese.
# Folder names are CrewChief identifiers and must stay in English; only the audio changes.
WORD_FOLDERS = {
    "point": "点",
    "hundred": "百",
    "thousand": "千",
    "ten_thousand": "万",     # no English equivalent, Chinese-only folder
    "oh": "零",
    "liang": "两",            # the "2" that precedes a measure word
    "minus": "负",
    "zerozero": "零零",       # CarNumber fallback
    "double_oh": "零零零",    # CarNumber fallback
    # Chinese has no singular/plural, so each pair below is the same word -- except minute,
    # where the two folders carry the two real Chinese forms.
    "hour": "小时",
    "hours": "小时",
    "minute": "分",           # laptimes: 一分二十三秒四
    "minutes": "分钟",        # durations: 还剩十五分钟
    "second": "秒",
    "seconds": "秒",
    "tenth": "秒",            # unused by NumberReaderZh, kept as a safety net
    "tenths": "秒",
}

# Optional whole-phrase recordings. NumberReaderZh.countWithUnit prefers these and falls back to
# concatenation when absent, so they are pure quality wins: they carry the tone sandhi on 一 and
# make 两 sound natural rather than spliced.
COMPOSITE_FOLDERS = {
    "1_hours": "一小时",
    "2_hours": "两小时",
    "1_minute": "一分",
    "2_minute": "两分",
    "1_minutes": "一分钟",
    "2_minutes": "两分钟",
    "1_seconds": "一秒",
    "2_seconds": "两秒",
    "1_thousand": "一千",
    "2_thousand": "两千",
    "1_ten_thousand": "一万",
    "2_ten_thousand": "两万",
}


def under_100(n: int) -> str:
    """0-99 as it is read on its own. 10 is 十, not 一十."""
    if n < 10:
        return DIGITS[n]
    if n < 20:
        return "十" + (DIGITS[n % 10] if n % 10 else "")
    return DIGITS[n // 10] + "十" + (DIGITS[n % 10] if n % 10 else "")


def build_rows():
    rows = []

    def add(folder, text):
        rows.append(
            {
                "audio_path": "\\voice\\numbers\\" + folder,
                "audio_filename": "1.wav",
                "subtitle": text,
                "text_for_tts": text,
                "original_english": folder,
            }
        )

    for n in range(100):
        add(str(n), under_100(n))
    # 01-09: read with the leading zero, for "一分零三秒". Splicing 零 + 三 sounds like two numbers.
    for n in range(1, 10):
        add("0%d" % n, "零" + DIGITS[n])
    for folder, text in WORD_FOLDERS.items():
        add(folder, text)
    for folder, text in COMPOSITE_FOLDERS.items():
        add(folder, text)
    return rows


# --------------------------------------------------------------------------------------------------
# Python mirror of NumberReaderZh.cs, used by --verify only.
# --------------------------------------------------------------------------------------------------

AVAILABLE = set()  # populated from the inventory, mirrors SoundCache.availableSounds


def _count_with_unit(count, unit_folder):
    combined = "numbers/%d_%s" % (count, unit_folder[len("numbers/"):])
    if combined in AVAILABLE:
        return [combined]
    head = ["numbers/liang"] if count == 2 else _read_whole(count, False)
    return head + [unit_folder]


def _read_under_100(n, has_higher_place):
    out = []
    if has_higher_place and 10 <= n < 20:
        out.append("numbers/1")
    out.append("numbers/%d" % n)
    return out


def _read_whole(n, has_higher_place):
    if n == 0:
        return ["numbers/0"]
    if n >= 10000:
        out = _count_with_unit(n // 10000, "numbers/ten_thousand")
        r = n % 10000
        if r:
            if r < 1000:
                out.append("numbers/oh")
            out += _read_whole(r, True)
        return out
    if n >= 1000:
        out = _count_with_unit(n // 1000, "numbers/thousand")
        r = n % 1000
        if r:
            if r < 100:
                out.append("numbers/oh")
            out += _read_whole(r, True)
        return out
    if n >= 100:
        out = ["numbers/%d" % (n // 100), "numbers/hundred"]
        r = n % 100
        if r:
            if r < 10:
                out.append("numbers/oh")
            out += _read_under_100(r, True)
        return out
    return _read_under_100(n, has_higher_place)


def read_integer(n):
    out = ["numbers/minus"] if n < 0 else []
    return out + _read_whole(abs(n), False)


# Precision, mirroring CrewChiefV4.NumberProcessing.Precision
HUNDREDTHS, TENTHS, SECONDS, MINUTES = "HUNDREDTHS", "TENTHS", "SECONDS", "MINUTES"


def read_time(hours, minutes, seconds, tenths, precision=TENTHS):
    out = []
    if hours > 0:
        out += _count_with_unit(hours, "numbers/hours")
    if minutes > 0:
        seconds_follow = hours == 0 and precision != MINUTES and (seconds > 0 or tenths > 0)
        out += _count_with_unit(minutes, "numbers/minute" if seconds_follow else "numbers/minutes")
    if not (hours > 0 or precision == MINUTES):
        tenths_follow = tenths > 0 and precision != SECONDS
        if minutes > 0 and seconds == 0 and tenths_follow:
            out += ["numbers/0", "numbers/seconds"]
        elif seconds > 0:
            if minutes > 0 and seconds < 10:
                out += ["numbers/0%d" % seconds, "numbers/seconds"]
            else:
                out += _count_with_unit(seconds, "numbers/seconds")
    if not (hours > 0 or tenths <= 0 or tenths >= 10 or precision in (SECONDS, MINUTES)):
        if minutes == 0 and seconds == 0:
            out += ["numbers/0", "numbers/point", "numbers/%d" % tenths, "numbers/seconds"]
        else:
            out += ["numbers/%d" % tenths]
    return out


def spoken(folders, text_by_folder):
    return "".join(text_by_folder[f[len("numbers/"):]] for f in folders)


INTEGER_CASES = [
    (0, "零"), (1, "一"), (2, "二"), (10, "十"), (12, "十二"), (20, "二十"), (23, "二十三"),
    (99, "九十九"), (100, "一百"), (105, "一百零五"), (110, "一百一十"), (115, "一百一十五"),
    (200, "二百"), (345, "三百四十五"), (305, "三百零五"), (999, "九百九十九"),
    (1000, "一千"), (1005, "一千零五"), (1015, "一千零一十五"), (1050, "一千零五十"),
    (1500, "一千五百"), (1505, "一千五百零五"), (1523, "一千五百二十三"), (2000, "两千"),
    # 两千 not 二千: matches the 2000 case above, and is what people actually say. Numbers this
    # large only ever show up as RPM anyway.
    (10000, "一万"), (10005, "一万零五"), (10500, "一万零五百"), (12345, "一万两千三百四十五"),
    (99999, "九万九千九百九十九"), (-5, "负五"),
]

# (hours, minutes, seconds, tenths, precision) -> expected reading
TIME_CASES = [
    ((0, 1, 23, 4, TENTHS), "一分二十三秒四"),
    ((0, 1, 23, 0, TENTHS), "一分二十三秒"),
    ((0, 1, 3, 4, TENTHS), "一分零三秒四"),
    ((0, 1, 0, 5, TENTHS), "一分零秒五"),
    ((0, 2, 23, 4, TENTHS), "两分二十三秒四"),
    ((0, 0, 0, 8, TENTHS), "零点八秒"),
    ((0, 0, 12, 3, TENTHS), "十二秒三"),
    ((0, 0, 12, 7, SECONDS), "十二秒"),
    ((0, 0, 2, 0, TENTHS), "两秒"),
    ((0, 0, 1, 0, TENTHS), "一秒"),
    ((0, 15, 0, 0, MINUTES), "十五分钟"),
    ((0, 2, 0, 0, MINUTES), "两分钟"),
    ((1, 30, 0, 0, MINUTES), "一小时三十分钟"),
    ((2, 0, 0, 0, MINUTES), "两小时"),
]


def verify(rows):
    text_by_folder = {r["audio_path"].rsplit("\\", 1)[1]: r["subtitle"] for r in rows}
    AVAILABLE.clear()
    AVAILABLE.update("numbers/" + f for f in text_by_folder)

    failures = 0
    print("=== 整数 ===")
    for n, expected in INTEGER_CASES:
        folders = read_integer(n)
        got = spoken(folders, text_by_folder)
        ok = got == expected
        failures += not ok
        print("%s %-7s %-16s %s" % ("✅" if ok else "❌", n, got,
                                    "" if ok else "期望 " + expected))

    print("\n=== 时间 ===")
    for (h, m, s, t, p), expected in TIME_CASES:
        folders = read_time(h, m, s, t, p)
        got = spoken(folders, text_by_folder)
        ok = got == expected
        failures += not ok
        label = "%d:%02d:%02d.%d %s" % (h, m, s, t, p)
        print("%s %-24s %-16s %s" % ("✅" if ok else "❌", label, got,
                                     "" if ok else "期望 " + expected))

    used = ({f for n, _ in INTEGER_CASES for f in read_integer(n)}
            | {f for a, _ in TIME_CASES for f in read_time(*a)})
    missing = sorted(used - AVAILABLE)
    if missing:
        failures += len(missing)
        print("\n❌ 清单缺少这些文件夹: " + ", ".join(missing))

    print("\n%d 个用例，%d 个失败" % (len(INTEGER_CASES) + len(TIME_CASES), failures))
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="translations/numbers_zh.csv")
    parser.add_argument("--verify", action="store_true",
                        help="Run the reading logic against known cases instead of writing the CSV.")
    args = parser.parse_args()

    rows = build_rows()

    if args.verify:
        sys.exit(1 if verify(rows) else 0)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["audio_path", "audio_filename", "subtitle", "text_for_tts", "original_english"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print("%d 个文件夹 -> %s" % (len(rows), args.out))


if __name__ == "__main__":
    main()
