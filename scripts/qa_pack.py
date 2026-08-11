"""
QA a generated voice pack against the inventory that produced it.

Checks every clip exists, is mono / 22050Hz / 16-bit, has no full-scale samples (clipping), and speaks at
a plausible rate. Short Chinese clips are where XTTS is least reliable -- a single character that comes
back at 1.5s has almost certainly hallucinated extra audio -- so the per-syllable rate is the headline
number rather than raw duration.

Usage:
    python3 scripts/qa_pack.py --phrase_inventory translations/numbers_zh.csv --pack output/Numbers
"""

import argparse
import csv
import os
import statistics
import sys
import wave

TARGET_RATE = 22050
TARGET_CHANNELS = 1
TARGET_WIDTH = 2

# Rate bounds in ms per syllable. Normal Mandarin sits near 170-200ms; anything far outside that is
# either clipped short or padded with hallucinated audio.
MIN_MS_PER_SYLLABLE = 90
MAX_MS_PER_SYLLABLE = 420


def syllable_count(text):
    """Han characters are one syllable each; everything else is ignored."""
    return sum(1 for ch in text if "一" <= ch <= "鿿") or 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phrase_inventory", required=True)
    parser.add_argument("--pack", required=True, help="Folder holding the generated voice/ tree")
    parser.add_argument("--max_ms_per_syllable", type=float, default=MAX_MS_PER_SYLLABLE)
    parser.add_argument("--min_ms_per_syllable", type=float, default=MIN_MS_PER_SYLLABLE)
    args = parser.parse_args()

    with open(args.phrase_inventory, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    problems = []
    durations = []
    rates = []
    checked = 0

    for row in rows:
        rel = row["audio_path"].replace("\\", "/").strip("/")
        path = os.path.join(args.pack, rel, row["audio_filename"])
        label = rel + "/" + row["audio_filename"]
        text = row["subtitle"]

        if not os.path.exists(path):
            problems.append("缺失      %-40s %s" % (label, text))
            continue

        with wave.open(path, "rb") as w:
            channels, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            raw = w.readframes(frames)

        checked += 1
        if (channels, width, rate) != (TARGET_CHANNELS, TARGET_WIDTH, TARGET_RATE):
            problems.append("格式      %-40s %dch/%dbit/%dHz" % (label, channels, width * 8, rate))

        duration = frames / float(rate)
        durations.append(duration)

        # 16-bit signed: a sample at either rail means the write clipped
        full_scale = sum(
            1
            for i in range(0, len(raw) - 1, 2)
            for v in (int.from_bytes(raw[i:i + 2], "little", signed=True),)
            if v >= 32767 or v <= -32768
        )
        if full_scale:
            problems.append("削波      %-40s %d 个满刻度样本" % (label, full_scale))

        ms_per_syllable = duration * 1000 / syllable_count(text)
        rates.append(ms_per_syllable)
        if ms_per_syllable > args.max_ms_per_syllable:
            problems.append("过长      %-40s %s  %.2fs / %d音节 = %.0fms"
                            % (label, text, duration, syllable_count(text), ms_per_syllable))
        elif ms_per_syllable < args.min_ms_per_syllable:
            problems.append("过短      %-40s %s  %.2fs / %d音节 = %.0fms"
                            % (label, text, duration, syllable_count(text), ms_per_syllable))

    print("%d/%d 条已检查" % (checked, len(rows)))
    if durations:
        print("时长      平均 %.2fs   范围 %.2f–%.2fs" % (
            statistics.mean(durations), min(durations), max(durations)))
        print("语速      中位 %.0fms/音节   范围 %.0f–%.0fms" % (
            statistics.median(rates), min(rates), max(rates)))

    if problems:
        print("\n%d 条异常：" % len(problems))
        for p in problems:
            print("  " + p)
    else:
        print("\n异常 0 条 ✅")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
