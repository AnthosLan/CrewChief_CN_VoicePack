"""
Translate the UI string CSV with a local Ollama model.

Not translate_phrases.py. That script's prompt is built for radio calls and three of its rules are
actively wrong here:

  - it tells the model to spell every numeral out as a word, but a settings screen needs digits
    ('Set to 0 to disable' must stay '0')
  - it asks for terse colloquial speech, which is the wrong register for a properties dialog
  - it knows nothing about '&' mnemonics or '{0}' placeholders, both of which appear in en.txt

What is shared is the glossary file and the corrections-CSV workflow, so the review step feels the
same as the four audio waves.

Mnemonics are handled in code rather than by the prompt: '&Stop' has its marker stripped before
translation and '(&S)' appended afterwards, which is the Chinese convention and removes an entire
class of model error.

Usage:
    python3 scripts/translate_uitext.py --in translations/ui_wave1.csv \
        --out translations/ui_wave1_zh.csv --glossary_file translations/glossary_zh.txt
"""

import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.request

MNEMONIC = re.compile(r"&([A-Za-z0-9])")

PROMPT = (
    'Respond with JSON only using this format: { "translation": "" }. '
    "DO NOT include notes, comments, or any other human-readable text. JSON only.\n"
    "You are translating the user interface of CrewChief, a desktop app for sim racing. "
    "The text appears on buttons, menu items, status labels, and settings screens.\n"
    "Rules:\n"
    "1. Keep Arabic numerals as digits. Do NOT spell them out as words.\n"
    "2. Use the register of Chinese software UI: short, plain, no exclamation marks, "
    "no colloquial particles like 了/吧/呢 unless the English is genuinely conversational.\n"
    "3. Preserve every {0}, {1} placeholder exactly as written, in a position that reads "
    "naturally in Chinese.\n"
    "4. Preserve every backslash character exactly -- it marks a forced line break.\n"
    "5. Do NOT translate: game names (Assetto Corsa, iRacing, rFactor, RaceRoom, Automobilista), "
    "product names (CrewChief, Ollama, SteamVR), key names (Alt, Ctrl, F1), file names, "
    "file extensions, and URLs. Leave them in English.\n"
    # Left to itself the model expands every abbreviation to its full product name, which turned
    # 'rF1 install path' and 'rF2 install path' into the same Chinese string.
    "6. NEVER expand an abbreviation. If the English says ACS, ACC, ACE, rF1, rF2, RBR, AMS, "
    "LMU, GSC, ASR, pCARS or R3E, write those exact letters. Do not replace them with the "
    "full product name, even when you know what they stand for.\n"
    "7. Do not add an equals sign to the translation.\n"
    "8. Translate what is written. Do not paraphrase, explain, or add words that are not there.\n"
    # 'R3E launch exe' came back as just 启动程序. Four settings rows collapsed onto one string.
    "9. Do not DROP words either. Every game name, abbreviation and qualifier in the English "
    "must still be present in the translation -- these strings sit next to each other in a "
    "settings list and the leading name is the only thing telling them apart.\n"
)


def build_prompt(english, key, glossary):
    prompt = PROMPT
    if glossary:
        prompt += ("\nUse these terms exactly as given. They override your own word choice:\n"
                   + glossary + "\n")
    # The key name is the best context available for a UI string: 'no_sound_pack_detected' tells
    # the model this is a status line about a missing file, which a bare English fragment does not.
    prompt += ("\nThis string's identifier in the source file is '%s'. Use it to resolve "
               "ambiguous words.\n" % key)
    prompt += "\nTranslate this user interface string from English to Simplified Chinese:\n\n"
    prompt += english
    return prompt


def call_ollama(prompt, model, host, temperature, timeout):
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "options": {"temperature": temperature},
        "stream": False,
    }).encode("utf-8")
    request = urllib.request.Request(
        "http://%s/api/generate" % host, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print("    ollama 调用失败：%s" % e)
        return None
    try:
        payload = json.loads(body.get("response", ""))
    except json.JSONDecodeError:
        print("    返回不是 JSON：%s" % body.get("response", "")[:100])
        return None
    if isinstance(payload, list):
        payload = payload[0] if payload else {}
    translation = (payload or {}).get("translation")
    return translation.strip() if isinstance(translation, str) and translation.strip() else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--glossary_file")
    parser.add_argument("--model", default="qwen2.5:14b")
    parser.add_argument("--ollama_host", default="localhost:11434")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--max_retries", type=int, default=3)
    parser.add_argument("--restart", action="store_true",
                        help="忽略已有输出重新翻译（改了 prompt 或术语表后必须加）")
    args = parser.parse_args()

    glossary = ""
    if args.glossary_file:
        with open(args.glossary_file, encoding="utf-8") as f:
            glossary = f.read().strip()

    with open(args.infile, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    done = {}
    if os.path.exists(args.out) and not args.restart:
        with open(args.out, newline="", encoding="utf-8") as f:
            existing = csv.reader(f)
            next(existing, None)
            for row in existing:
                if len(row) == 4 and row[2].strip():
                    done[row[1]] = row[2].strip()
        # Silence here is how a prompt change gets quietly ignored -- say what is being reused.
        print("续跑：已有 %d 条译文，跳过（改了 prompt 或术语表请加 --restart）\n" % len(done))

    # Identical English appears under several keys ('Cancel', 'Close'). Seed the cache from the
    # resumed rows so a restart does not re-ask for strings it already has an answer for.
    cache = {}
    for row in rows:
        if row[1] in done:
            cache.setdefault(row[3], done[row[1]])

    total = len(rows)
    translated = 0
    for index, row in enumerate(rows, 1):
        _section, key, _zh, english = row
        if key in done:
            row[2] = done[key]
            continue

        # Strip the mnemonic marker before translating and re-attach it in the Chinese
        # convention afterwards: '&Stop' -> '停止(&S)'.
        mnemonic = MNEMONIC.search(english)
        clean = MNEMONIC.sub(r"\1", english) if mnemonic else english

        result = cache.get(clean)
        if result is None:
            prompt = build_prompt(clean, key, glossary)
            for attempt in range(args.max_retries):
                result = call_ollama(prompt, args.model, args.ollama_host,
                                     args.temperature, args.timeout)
                if result:
                    break
                print("    第 %d 次重试 %s" % (attempt + 1, key))
            if not result:
                print("  [%d/%d] %s —— 放弃，留空待人工补" % (index, total, key))
                continue
            cache[clean] = result

        if mnemonic:
            # The marker belongs to the line it was on, not to the end of the string. '&Start Crew
            # Chief\Auto detect active' is two rendered lines, and appending blindly put the
            # shortcut on the second one. Segments are matched by index -- the model keeps the '\'
            # count -- and anything unexpected falls back to the end.
            marker = "(&%s)" % mnemonic.group(1).upper()
            en_segments = english.split("\\")
            hit = next((i for i, s in enumerate(en_segments) if MNEMONIC.search(s)), 0)
            zh_segments = result.split("\\")
            if hit < len(zh_segments):
                zh_segments[hit] += marker
                result = "\\".join(zh_segments)
            else:
                result += marker
        row[2] = result
        translated += 1
        print("  [%d/%d] %s\n        %s\n        %s" % (index, total, key, english, result))

        # Write after every row: a 1400-row wave is a long run and losing it to a crash at row
        # 1300 means paying for all of it again.
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    missing = sum(1 for row in rows if not row[2].strip())
    print("\n%d 条 -> %s" % (len(rows), args.out))
    print("  本次翻译 %d 条，复用 %d 条" % (translated, len(done)))
    if missing:
        print("  ⚠️  %d 条没有译文，重跑一次或人工补" % missing)
        sys.exit(1)


if __name__ == "__main__":
    main()
