"""
Convert CrewChief's ui_text/en.txt to a translation CSV and back.

The UI strings are a flat 'key = value' file, not the audio inventory format, so they get their
own converter rather than being forced through make_chief_inventory.py. What they do share is the
wave workflow: cut a slice, translate it, review it, apply corrections, convert back.

Parsing deliberately mirrors Configuration.merge() (Configuration.cs:213) rather than being
"correct", because whatever that method does is what CrewChief actually loads:

  - a comment is a line whose FIRST character is '#'  (no trimming -- indented '#' is not a comment)
  - a line without '=' is skipped
  - the key is everything before the first '=', trimmed
  - duplicate keys: last definition wins (the method does Remove() then Add())

One place we do NOT mirror it: merge() takes line.Split('=')[1], so a value containing '=' is
truncated at the first one. Two English help strings are already broken this way upstream. We keep
the whole value here so the translator sees the real sentence, and qa_uitext.py refuses any '='
in the Chinese -- there is no reason to reproduce the bug in a new language.

Usage:
    python3 scripts/make_uitext_inventory.py --list_waves
    python3 scripts/make_uitext_inventory.py --wave 1 --out translations/ui_wave1.csv
    python3 scripts/make_uitext_inventory.py --to_txt translations/ui_wave1_final.csv \
        --out src/ui_text_zh.txt
"""

import argparse
import csv
import os
import re
import sys

DEFAULT_EN = os.path.expanduser("~/Projects/CrewChiefV4-main/CrewChiefV4/ui_text/en.txt")

# Section headers in en.txt are '###### Title ######' lines. The titles are display text, so they
# are mapped to stable slugs here -- a wave definition that keyed off the English title would break
# the moment upstream renames a header.
SECTION_SLUGS = [
    ("UI", "main_window"),
    ("Menu bar", "menu_bar"),
    ("", "voice_and_controls"),          # untitled header at line 92: SRE modes + controller binding
    ("My Name dialog", "my_name_dialog"),
    ("Opponent Names dialog", "opponent_names_dialog"),
    ("Opponent Name Selection dialog", "opponent_name_selection"),
    ("Macro Editor", "macro_editor"),
    ("Action Editor", "action_editor"),
    ("SteamVR Overlay Settings", "steamvr_overlay"),
    ("Trace Playback Window", "trace_playback"),
    ("Preferences", "preferences"),
]

# Wave 3 is every _help/_tooltip string regardless of section: they are long-form prose with a
# hard formatting rule (see qa_uitext.py), so they are reviewed together rather than scattered
# through the other three waves.
WAVES = {
    1: dict(
        name="主界面与菜单",
        sections=["main_window", "menu_bar", "voice_and_controls",
                  "my_name_dialog", "opponent_names_dialog"],
        long_form=False,
    ),
    2: dict(name="Preferences 属性名", sections=["preferences"], long_form=False),
    3: dict(name="帮助与提示长文本", sections=None, long_form=True),
    4: dict(
        name="次要对话框",
        sections=["opponent_name_selection", "macro_editor", "action_editor",
                  "steamvr_overlay", "trace_playback"],
        long_form=False,
    ),
}

HEADER = ["section", "key", "zh", "english"]


# Keys whose value is an identifier the app parses, not text it shows. Translating any of these
# breaks behaviour silently -- the string still loads, it just stops matching:
#
#   _category  Enum.TryParse into PropertyCategory (PropertyFilter.cs:46). A translated value
#              fails to parse and the property drops out of its settings group.
#   _filter    Enum.TryParse into GameEnum, '!' prefix means exclude (PropertyFilter.cs:59).
#              A translated value makes the property show up under every game, or none.
#   _metadata  compared with == "RESTART_REQUIRED" (PropertiesForm.cs). A translated value
#              means the 'restart required' warning never appears.
#
#   _listprop_type  a fully-qualified C# type name fed to Type.GetType(name, throwOnError: true)
#              (ListPropertyControl.cs:22). This one does not fail quietly -- it throws. Only 4
#              keys, and the model translated all four ('CrewChiefV4.Audio.MinPriorityForInterrupt'
#              came back as 'CrewChiefV4.音频.最低优先级中断').
#
# This is the UI's version of "文件夹名不能翻译": the 909 _category/_filter/_metadata values are
# all identifier-shaped (^!?[A-Z0-9_]+(;[A-Z0-9_]+)*$), verified against en.txt. Their display
# labels live in separate *_category_label and *_listprop_value_N keys, which ARE translated.
#
# Note that _exe / _params / _port / _path are NOT in this list -- despite the machine-ish names
# they hold real labels ('ACS install path', 'ACC UDP port').
INVARIANT_SUFFIXES = ("_category", "_filter", "_metadata", "_listprop_type")


def is_invariant(key):
    return key.endswith(INVARIANT_SUFFIXES)


def is_long_form(key):
    """_help and _tooltip are the keys Configuration runs through the line-wrapper."""
    return key.endswith("_help") or key.endswith("_tooltip")


# Keys that get run through NewlinesInLongString, and the maxLength each is called with.
# _help and _tooltip are wrapped by Configuration.getUIStringMaybeNull itself; these four are
# wrapped by their call sites instead, so they need the same rule despite the name not saying so.
EXPLICIT_WRAP_LIMITS = {
    "enter_your_name": 44,                        # MyName-V.cs:32, getUIStringWrapped default
    "install_plugin_popup_create_text": 44,       # PluginInstaller.cs:126, same
    "install_any_speechlanguage_popup_text": 55,  # SpeechRecogniser.cs, direct call
    "install_speechplatform_popup_text": 55,      # SpeechRecogniser.cs, direct call
}
DEFAULT_WRAP_LIMIT = 44


def wrap_limit(key):
    """The maxLength this key is wrapped at, or None if CrewChief never wraps it."""
    if key in EXPLICIT_WRAP_LIMITS:
        return EXPLICIT_WRAP_LIMITS[key]
    if is_long_form(key):
        return DEFAULT_WRAP_LIMIT
    return None


def parse_en(path):
    """
    Returns [(section_slug, key, value)] in file order, deduplicated the way CrewChief does it.
    """
    slug_by_title = dict(SECTION_SLUGS)
    section = "main_window"
    seen = {}
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            header = re.match(r"^#{6,}(.*?)#{6,}\s*$", line)
            if header:
                title = header.group(1).strip()
                if title in slug_by_title:
                    section = slug_by_title[title]
                else:
                    sys.exit("en.txt 里出现未知分区标题 %r，请先在 SECTION_SLUGS 里登记" % title)
                continue
            # Deliberately not line.strip().startswith -- see module docstring.
            if line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if not key:
                continue
            if key in seen:
                # Last definition wins, so overwrite in place and keep the original position.
                rows[seen[key]] = (section, key, value)
            else:
                seen[key] = len(rows)
                rows.append((section, key, value))
    return rows


def select(rows, wave):
    spec = WAVES[wave]
    out = []
    for section, key, value in rows:
        if is_invariant(key):
            continue
        if is_long_form(key) != spec["long_form"]:
            continue
        if spec["sections"] is not None and section not in spec["sections"]:
            continue
        out.append((section, key, value))
    return out


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for section, key, value in rows:
            writer.writerow([section, key, "", value])
    print("%d 条 -> %s" % (len(rows), path))


def to_txt(csv_paths, out_path, en_path):
    """
    Merge one or more finished wave CSVs into a single zh.txt.

    Untranslated keys are omitted rather than written empty: Configuration merges this file on top
    of en.txt, so a missing key falls back to English while an empty one would blank the label.
    """
    en_order = {key: i for i, (_, key, _) in enumerate(parse_en(en_path))}
    by_section = {}
    total = 0
    for path in csv_paths:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            head = next(reader, None)
            if head != HEADER:
                sys.exit("%s 的表头不是 %s" % (path, ",".join(HEADER)))
            for row in reader:
                if len(row) != 4:
                    sys.exit("%s 有 %d 个字段的行，应为 4 个：\n    %s"
                             % (path, len(row), ",".join(row)))
                section, key, zh, _english = row
                if not zh.strip():
                    continue
                by_section.setdefault(section, []).append((key, zh.strip()))
                total += 1

    slug_order = [slug for _, slug in SECTION_SLUGS]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# CrewChief 中文界面文本\n")
        f.write("# 由 scripts/make_uitext_inventory.py --to_txt 生成，不要手工编辑。\n")
        f.write("# 未翻译的 key 不写在这里，CrewChief 会自动回落到 en.txt 的英文。\n")
        for slug in slug_order:
            entries = by_section.get(slug)
            if not entries:
                continue
            entries.sort(key=lambda kv: en_order.get(kv[0], 1 << 30))
            f.write("\n###################################### %s ######\n" % slug)
            for key, zh in entries:
                f.write("%s = %s\n" % (key, zh))
    print("%d 条 -> %s" % (total, out_path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--en", default=DEFAULT_EN, help="CrewChief 的 ui_text/en.txt")
    parser.add_argument("--wave", type=int, choices=sorted(WAVES))
    parser.add_argument("--to_txt", nargs="+", metavar="CSV",
                        help="把定稿 CSV 转回 zh.txt，可传多个波次")
    parser.add_argument("--out")
    parser.add_argument("--list_waves", action="store_true", help="只打印各波条数，不写文件")
    args = parser.parse_args()

    if not os.path.exists(args.en):
        sys.exit("找不到 %s —— CrewChiefV4-main 需要平级放在 ~/Projects/ 下" % args.en)

    if args.to_txt:
        if not args.out:
            sys.exit("--to_txt 需要 --out")
        to_txt(args.to_txt, args.out, args.en)
        return

    rows = parse_en(args.en)

    if args.list_waves:
        invariant = sum(1 for _s, key, _v in rows if is_invariant(key))
        print("en.txt 共 %d 条（去重后）" % len(rows))
        print("  其中 %d 条是标识符不译（%s），剩 %d 条待译\n"
              % (invariant, "/".join(INVARIANT_SUFFIXES), len(rows) - invariant))
        covered = 0
        for wave in sorted(WAVES):
            picked = select(rows, wave)
            covered += len(picked)
            print("  U%d  %-16s %5d 条" % (wave, WAVES[wave]["name"], len(picked)))
        print("\n  合计 %d 条" % covered)
        if covered != len(rows) - invariant:
            # Every translatable string must land in exactly one wave, or the ones that fall
            # through get silently left in English with nothing to show they were considered.
            sys.exit("\n⚠️  波次划分没有覆盖全部 %d 条待译，差 %d 条"
                     % (len(rows) - invariant, len(rows) - invariant - covered))
        return

    if not args.wave or not args.out:
        sys.exit("需要 --wave N --out FILE（或 --list_waves / --to_txt）")

    write_csv(select(rows, args.wave), args.out)


if __name__ == "__main__":
    main()
