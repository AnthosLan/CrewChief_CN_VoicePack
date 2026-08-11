"""
Build the crew-chief phrase inventory for phase 2, straight from CrewChief's own subtitles.csv.

autovoicepack's extra/generate_phrase_inventory.py is close but not usable as-is:
  - audio_path comes out relative to the voice dir, so the leading '\\voice' segment is missing.
    translate_phrases.py matches --exclude_paths / --only_paths against 'voice/xxx', so every
    prefix silently fails to match and nothing gets excluded.
  - it emits 4 columns; this repo's format carries a 5th, original_english, for manual review.
  - it dumps all 60 categories including the 24 alternative-voice ones we skip.

Splitting by wave keeps each batch independently shippable -- see the phase 2 plan in
docs/中文语音包制作方案.md §9.

Usage:
    python3 scripts/make_chief_inventory.py --list_waves
    python3 scripts/make_chief_inventory.py --wave 1 --out translations/chief_wave1.csv
    python3 scripts/make_chief_inventory.py --wave all --out translations/chief_all.csv
"""

import argparse
import csv
import os
import sys

DEFAULT_VOICE_DIR = os.path.expanduser(
    "~/Projects/CrewChiefV4-main/CrewChiefV4/sounds/voice")

# Ordered by how often you actually hear it in a race, so wave 1 buys the most audible progress.
WAVES = {
    1: ["flags", "lap_times", "position", "acknowledge", "timings", "lap_counter", "fuel"],
    2: ["tyre_monitor", "penalties", "damage_reporting", "conditions", "opponents",
        "push_now", "race_time"],
    3: ["mandatory_pit_stops", "multiclass", "battery", "frozen_order", "watched_opponents",
        "strategy", "overtaking_aids", "driver_swaps", "engine_monitor"],
    4: ["pearls_of_wisdom", "rants", "incidents", "alarm_clock", "licence", "rejoining"],
}

# Already shipped in v0.1.0.
DONE = ["spotter", "radio_check", "numbers"]

# Deliberately skipped -- reasons in docs/中文语音包制作方案.md §3.2.
SKIP_EXACT = ["corners", "pace_notes"]
SKIP_PREFIX = ["spotter_", "radio_check_", "codriver"]


def classify(category):
    """Return 'done', 'skip', a wave number, or None if the category is unaccounted for."""
    if category in DONE:
        return "done"
    if category in SKIP_EXACT:
        return "skip"
    for prefix in SKIP_PREFIX:
        if category.startswith(prefix):
            return "skip"
    for wave, categories in WAVES.items():
        if category in categories:
            return wave
    return None


def read_subtitles(path):
    """subtitles.csv is 'N.wav,"english text"' with no header."""
    mapping = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                mapping[row[0].strip()] = row[1].strip()
    return mapping


def gather(voice_dir, wanted_categories):
    """Walk voice/<category>/<folder>/ and pair each wav with its subtitle."""
    rows = []
    missing_subtitles = []
    for category in sorted(os.listdir(voice_dir)):
        if category not in wanted_categories:
            continue
        category_dir = os.path.join(voice_dir, category)
        if not os.path.isdir(category_dir):
            continue
        for folder in sorted(os.listdir(category_dir)):
            folder_dir = os.path.join(category_dir, folder)
            if not os.path.isdir(folder_dir):
                continue
            wavs = sorted(f for f in os.listdir(folder_dir) if f.endswith(".wav"))
            if not wavs:
                continue
            subtitles_path = os.path.join(folder_dir, "subtitles.csv")
            subtitles = read_subtitles(subtitles_path) if os.path.exists(subtitles_path) else {}
            if not subtitles:
                missing_subtitles.append("%s/%s (%d wav)" % (category, folder, len(wavs)))
                continue
            for wav in wavs:
                english = subtitles.get(wav)
                if not english:
                    continue
                # Backslashes and the leading \voice are what CrewChief and translate_phrases.py
                # both expect. Every segment is an identifier -- never translate a folder name.
                audio_path = "\\voice\\%s\\%s" % (category, folder)
                # subtitle / text_for_tts still hold English here; the translation step
                # overwrites both and leaves original_english as the review reference.
                rows.append([audio_path, wav, english, english, english])
    return rows, missing_subtitles


def list_waves(voice_dir):
    unclassified = []
    for category in sorted(os.listdir(voice_dir)):
        if not os.path.isdir(os.path.join(voice_dir, category)):
            continue
        if classify(category) is None:
            unclassified.append(category)

    total_rows = 0
    for wave in sorted(WAVES):
        rows, _ = gather(voice_dir, WAVES[wave])
        phrases = len(set(r[4] for r in rows))
        total_rows += len(rows)
        print("波次 %d  %2d 个分类  %5d 个音频  %4d 条去重文案" % (
            wave, len(WAVES[wave]), len(rows), phrases))
        print("        " + " ".join(WAVES[wave]))
    print("-" * 58)
    print("合计 %d 个音频" % total_rows)
    if unclassified:
        print("\n⚠️  未归类的分类（既不在波次里也不在跳过表里）: " + ", ".join(unclassified))
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice_dir", default=DEFAULT_VOICE_DIR,
                        help="CrewChief 官方 voice 目录（提供 subtitles.csv 权威台本）")
    parser.add_argument("--wave", default="all",
                        help="1/2/3/4 或 all")
    parser.add_argument("--out", default="translations/chief_zh.csv")
    parser.add_argument("--list_waves", action="store_true",
                        help="只打印波次构成，不写文件")
    args = parser.parse_args()

    if not os.path.isdir(args.voice_dir):
        sys.exit("找不到 voice 目录: %s" % args.voice_dir)

    if args.list_waves:
        sys.exit(list_waves(args.voice_dir))

    if args.wave == "all":
        wanted = [c for categories in WAVES.values() for c in categories]
    else:
        try:
            wanted = WAVES[int(args.wave)]
        except (ValueError, KeyError):
            sys.exit("--wave 只能是 1/2/3/4 或 all")

    rows, missing = gather(args.voice_dir, wanted)
    if not rows:
        sys.exit("没有收集到任何行，检查 --voice_dir")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["audio_path", "audio_filename", "subtitle",
                         "text_for_tts", "original_english"])
        writer.writerows(rows)

    print("%d 个音频 / %d 条去重文案 -> %s" % (
        len(rows), len(set(r[4] for r in rows)), args.out))
    if missing:
        print("\n⚠️  这些文件夹有 wav 但没有 subtitles.csv，已跳过，需要另找台本：")
        for item in missing:
            print("    " + item)


if __name__ == "__main__":
    main()
