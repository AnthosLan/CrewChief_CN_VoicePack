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
import re
import sys

DEFAULT_VOICE_DIR = os.path.expanduser(
    "~/Projects/CrewChiefV4-main/CrewChiefV4/sounds/voice")

# Ordered by how often you actually hear it in a race, so wave 1 buys the most audible progress.
WAVES = {
    1: ["flags", "lap_times", "position", "acknowledge", "timings", "lap_counter", "fuel"],
    2: ["tyre_monitor", "penalties", "damage_reporting", "conditions", "opponents",
        "push_now", "race_time"],
    3: ["mandatory_pit_stops", "multiclass", "battery", "frozen_order", "watched_opponents",
        "strategy", "driver_swaps", "engine_monitor"],
    4: ["pearls_of_wisdom", "rants", "incidents", "alarm_clock", "licence", "rejoining"],
}

# 29 folders have wav files but no subtitles.csv -- newer messages that shipped without subtitles.
# autovoicepack's older inventory doesn't have them either, so the text was recovered by tracing the
# folder constant in the CrewChief source and reading its trigger condition. Emitted by --manual,
# already in Chinese, so they bypass translation and go straight to TTS.
#
# ⚠️ Two of these are fragments concatenated with a number, so Chinese word order matters:
#   race_starts_in            MessageContents(folder, time, "timings/seconds")  -> prefix
#   drs_activations_remaining number precedes the folder                        -> suffix
MANUAL_TEXT = {
    "damage_reporting/damage": ("车有损伤", "we have damage"),
    "flags/red-yellow-flag": ("红黄旗，路面有异物", "red and yellow flag"),
    "flags/slippery-surface-flag": ("路面湿滑", "slippery surface"),
    "fuel/not_enough_laps_for_average": ("圈数不够，算不出平均油耗", "not enough laps for average"),
    "lap_counter/has_taken_the_win": ("拿下了胜利", "has taken the win"),
    "lap_counter/race_starts_in": ("比赛开始还有", "race starts in"),
    "mandatory_pit_stops/no_pit_timings_unreliable_fuel_estimates":
        ("拿不到进站时间，油耗预估不准", "no pit timings, fuel estimates unreliable"),
    "mandatory_pit_stops/no_pit_timings_unreliable_position_estimates":
        ("拿不到进站时间，位置预估不准", "no pit timings, position estimates unreliable"),
    "overtaking_aids/drs_activations_remaining": ("次 DRS 可用", "DRS activations remaining"),
    "overtaking_aids/no_drs_activations_remaining": ("DRS 用完了", "no DRS activations remaining"),
    "overtaking_aids/one_drs_activation_remaining": ("还剩一次 DRS", "one DRS activation remaining"),
    "overtaking_aids/remember_to_use_kers": ("别忘了用 KERS", "remember to use KERS"),
    "penalties/disqualified_no_headlights": ("没开大灯，被取消资格", "disqualified, no headlights"),
    "penalties/slow_down_penalty_clear": ("减速罚时已解除", "slow down penalty clear"),
    "penalties/warning_headlights_required_when_raining":
        ("雨天必须开大灯", "headlights required when raining"),
    "timings/car_behind_is_lapping_us": ("后车要套我们圈", "car behind is lapping us"),
    "timings/car_behind_is_unlapping_itself": ("后车在解套", "car behind is unlapping itself"),
}

# The other 12 have no subtitles either, but nothing to make: not speech, or the event never
# fires in AC. Listed explicitly so they stop showing up as "missing text" every run.
DROP = {
    "acknowledge/breath_in": "吸气声，不是语音（AudioPlayer.cs:1694 直接播放，受 enable_breath_in 控制）",
    "lap_counter/strength_of_field_is": "Ratings.cs，iRacing/R3E 专属，AC 不加载",
    "lap_counter/strength_of_field_for_our_class_is": "同上",
    "flags/stay_below_vsc_speed": "虚拟安全车，AC 没有",
    "flags/virtual_safety_car": "同上",
    "flags/virtual_safety_car_phase_over": "同上",
    "flags/virtual_safety_car_speed": "同上",
    "penalties/vsc_violation_penalty": "同上",
    "fuel/virtual_energy": "LMU 的虚拟能量，.cs 里零引用",
    "damage_reporting/wheel_damage": ".cs 里零引用，死音频",
    "rejoining/rejoin_clear": "rejoin 只出现在 F1/LMU 的数据结构里，没有播报路径",
    "rejoining/rejoin_wait": "同上",
}

# Stock car procedures. Every one of these hangs off GameStateData.StockCarRulesData, which only
# iRacingGameStateMapper and RF2GameStateMapper ever populate -- both AC mappers (ACS/, ACS128/)
# reference it zero times, so none of it can fire in AC. 20 folders / 89 audio files.
#
# Not in DROP: flags/fc_yellow_pits_* looks American but is chosen by
# GlobalBehaviourSettings.useAmericanTerms, a user preference, and does fire in AC.
#
# Dropping is safe even if this reasoning is ever wrong: the pack overlays a copy of the English
# pack, so a folder we don't ship keeps playing its original English audio rather than going silent.
DROP_OVAL_PATTERN = "lucky_dog|wave_around|waved_around|pace_car|tri-oval|move_to_choose_lane"

# Car class designations (GT3, GT300, LMP2, DTM, Group C...) keep the original English audio, for
# the same reason driver names and corner names do: Chinese drivers say them in English anyway.
# There is also a practical reason -- XTTS reading Latin acronyms through its Chinese frontend is
# unreliable. 'GTC' came out at 1.7s for three letters, and 'DTM赛车' truncated to 0.21s.
# 34 folders / 103 audio files. Not shipping them leaves the English original in place.
DROP_CLASS_PATTERN = ("^(gt\\d*|gtc|gte|gtlm|gto|gtp|lmdh|lmp\\d|tc\\d|dtm|carrera_cup"
                      "|group\\d|group[abc])(_runners|_cars|_class_cars)?$")

# Already shipped in v0.1.0.
DONE = ["spotter", "radio_check", "numbers"]

# Deliberately skipped -- reasons in docs/中文语音包制作方案.md §3.2.
# overtaking_aids is DRS / KERS / push-to-pass -- English acronyms end to end. XTTS reading them
# through its Chinese frontend gave DRS only 0.25s inside a sentence, less than three letter names
# need. Same call as the car classes: leave the English original in place.
SKIP_EXACT = ["corners", "pace_notes", "overtaking_aids"]
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


def gather(voice_dir, wanted_categories, manual=False):
    """
    Walk voice/<category>/<folder>/ and pair each wav with its text.

    manual=False yields the rows awaiting translation (English in subtitle / text_for_tts).
    manual=True yields only the MANUAL_TEXT folders, already in Chinese, so the two sets never
    mix -- feeding pre-translated rows back through translate_phrases.py would translate them again.
    """
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
            key = "%s/%s" % (category, folder)
            if key in DROP or re.search(DROP_OVAL_PATTERN, folder) \
                    or (category == "multiclass" and re.match(DROP_CLASS_PATTERN, folder.lower())):
                continue
            wavs = sorted(f for f in os.listdir(folder_dir) if f.endswith(".wav"))
            if not wavs:
                continue
            # Backslashes and the leading \voice are what CrewChief and translate_phrases.py
            # both expect. Every segment is an identifier -- never translate a folder name.
            audio_path = "\\voice\\%s\\%s" % (category, folder)

            if key in MANUAL_TEXT:
                if not manual:
                    continue
                chinese, english = MANUAL_TEXT[key]
                for wav in wavs:
                    rows.append([audio_path, wav, chinese, chinese, english])
                continue
            if manual:
                continue

            subtitles_path = os.path.join(folder_dir, "subtitles.csv")
            subtitles = read_subtitles(subtitles_path) if os.path.exists(subtitles_path) else {}
            if not subtitles:
                missing_subtitles.append("%s (%d wav)" % (key, len(wavs)))
                continue
            for wav in wavs:
                english = subtitles.get(wav)
                if not english:
                    continue
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
    parser.add_argument("--manual", action="store_true",
                        help="只导出手写中文的那批（官方没有 subtitles.csv），已是中文，不要再送去翻译")
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

    rows, missing = gather(args.voice_dir, wanted, manual=args.manual)
    if not rows:
        sys.exit("这一波没有手写中文的行" if args.manual else "没有收集到任何行，检查 --voice_dir")

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
