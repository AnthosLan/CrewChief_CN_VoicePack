"""
Standalone pilot generator for Apple Silicon / any machine without Docker or CUDA.

The project's normal path is a CUDA Docker image (nvidia/cuda base, deepspeed,
xtts-integrity, sox). None of that runs on an M-series Mac, but a 10-phrase pilot
does not need any of it -- the point of a pilot is to answer one question:

    does XTTS v2 produce usable Chinese in this voice, at radio-call length?

So this script keeps only what affects that answer:
  - the same low-level Xtts inference call as generate_voice_pack.py, with the
    same temperature/top_k/top_p/repetition_penalty and a --language argument
  - the same sox post-processing chain, reimplemented with torchaudio so no
    external binaries are required
  - the same phrase-inventory CSV format, so the pilot file transfers unchanged
    to a real GPU box later

It deliberately does NOT include: deepspeed, the xtts-integrity validity model,
variation generation, or the retry loop. Judge the raw output by ear.

Setup (once):
    pip install coqui-tts

The XTTS v2 model (~1.9GB) downloads automatically on first run. Note that XTTS v2
is released under the Coqui Public Model License, which is NON-COMMERCIAL. The
downloader will ask you to accept it interactively; exporting COQUI_TOS_AGREED=1
accepts it non-interactively. Read the licence before doing that, particularly if
this voice pack is ever going to be distributed.

Usage:
    python3 pilot_mac.py --phrase_inventory translated/pilot_zh.csv --language zh-cn
"""

import argparse
import csv
import glob
import logging
import os
import time

import torch
import torchaudio
import torchaudio.functional as AF

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# CrewChief's own sound pack format, confirmed against the shipped voice files:
# mono, 22050Hz, 16-bit PCM.
TARGET_SAMPLE_RATE = 22050

# Post-processing presets, as (equalizer bands, overdrive).
# Each band is (center_freq_hz, gain_db, Q); overdrive is (gain, colour) or None.
#
# 'radio' is the curve from apply_audio_effects() in generate_voice_pack.py. It
# scoops 12dB at 100Hz, which is below the fundamental of most male voices, and
# lifts 6dB of presence on top. That reads as authentic narrow-band radio on the
# original human recordings, but TTS output is already thin, so the same curve
# leaves it sounding hollow. The other presets walk that back by degrees.
EQ_PRESETS = {
    "radio": (
        [(100, -12, 0.5), (200, -6, 0.5), (300, -3, 0.5),
         (3000, 6, 0.5), (6000, 4, 0.5), (10000, 3, 0.5)],
        (7.0, 12.0),
    ),
    "warm": (
        [(100, -6, 0.5), (200, -2, 0.5), (300, 0, 0.5),
         (3000, 3, 0.5), (6000, 2, 0.5), (10000, 1, 0.5)],
        (3.0, 8.0),
    ),
    "full": (
        [(100, -2, 0.5), (250, 1, 0.7), (3000, 2, 0.7), (8000, 1, 0.7)],
        None,
    ),
    "broadcast": (
        # chest weight back in at 120Hz, mud cut at 400Hz, controlled presence
        [(120, 2, 0.7), (400, -3, 0.8), (2500, 3, 0.7), (5000, 2, 0.7)],
        (2.0, 8.0),
    ),
}


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Generate a small CrewChief voice pack pilot locally, without Docker or CUDA."
    )
    parser.add_argument(
        "--phrase_inventory",
        default="translated/pilot_zh.csv",
        help="CSV in the phrase_inventory.csv format: audio_path, audio_filename, subtitle, text_for_tts[, original_english]",
    )
    parser.add_argument(
        "--language",
        default="zh-cn",
        help="XTTS language code. Must match the language of text_for_tts.",
    )
    parser.add_argument(
        "--voice_name", default="ChiefZH", help="Output folder name for this voice."
    )
    parser.add_argument(
        "--your_name",
        default="车手",
        help="Substituted for the YOUR_NAME placeholder in the inventory text.",
    )
    parser.add_argument(
        "--baseline_audio_dir",
        default="./baseline/Luis",
        help="Folder of reference .wav clips to clone. The bundled Luis is an English speaker -- for a Chinese pack, 3 clips of a Chinese speaker will sound considerably better.",
    )
    parser.add_argument("--output_audio_dir", default="./output_pilot")
    parser.add_argument(
        "--xtts_speed",
        type=float,
        default=1.6,
        help="Matches the default in generate_voice_pack.py. Drop to ~1.3 if Chinese output clips its own syllables.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cpu", "mps"],
        help="'auto' prefers mps on Apple Silicon. Fall back to cpu if you hit an unimplemented-operator error.",
    )
    parser.add_argument(
        "--eq_preset",
        default="radio",
        choices=sorted(EQ_PRESETS),
        help="Post-processing character. 'radio' is the original project curve; 'warm' and 'full' progressively restore the low end that curve removes; 'broadcast' puts chest weight back and cuts mud instead.",
    )
    parser.add_argument(
        "--artifact_trim_max_syllables",
        type=int,
        default=4,
        help="Clips this short (in Han characters) get their hallucinated tail cut -- see drop_trailing_artifact. Set to 0 to disable.",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=1,
        help="Generate this many candidates per phrase and keep the shortest plausible one. Short Chinese prompts need 3-5; long phrases are stable at 1.",
    )
    parser.add_argument(
        "--attempts_max_syllables",
        type=int,
        default=6,
        help="Only phrases this short get multiple attempts -- longer ones are stable and would just cost time. 0 applies --attempts to everything.",
    )
    parser.add_argument(
        "--min_ms_per_syllable",
        type=float,
        default=90.0,
        help="Floor for candidate selection: anything faster than this is assumed truncated, not good.",
    )
    parser.add_argument(
        "--disable_audio_effects",
        action="store_true",
        help="Skip the EQ / trim / normalise stage and keep the raw model output.",
    )
    parser.add_argument(
        "--keep_raw",
        action="store_true",
        help="Also write the pre-effects .raw.wav next to each output, for A/B comparison.",
    )
    return parser.parse_args()


def resolve_device(requested: str) -> torch.device:
    if requested == "auto":
        if torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    return torch.device(requested)


def load_model(device: torch.device):
    """
    Download (first run only) and load XTTS v2, mirroring generate_voice_pack.py's
    low-level setup but without deepspeed, which is CUDA-only.
    """
    from TTS.tts.configs.xtts_config import XttsConfig
    from TTS.tts.models.xtts import Xtts
    from TTS.utils.manage import ModelManager

    model_id = "tts_models/multilingual/multi-dataset/xtts_v2"
    manager = ModelManager()
    logging.info("Locating XTTS v2 (downloads ~1.9GB on first run)...")
    model_path, _, _ = manager.download_model(model_id)

    config = XttsConfig()
    config.load_json(os.path.join(model_path, "config.json"))
    model = Xtts.init_from_config(config)
    model.load_checkpoint(config, checkpoint_dir=model_path, use_deepspeed=False)
    model.to(device)
    model.eval()
    logging.info(f"Model loaded on {device}")
    return model


def trim_silence(wav: torch.Tensor, threshold: float) -> torch.Tensor:
    """
    Equivalent of the sox `silence 1 0.1 X% / reverse / silence / reverse` pair:
    drop leading and trailing samples below a fraction of full scale.
    """
    mask = wav.abs().max(dim=0).values > threshold
    nonzero = torch.nonzero(mask, as_tuple=False)
    if nonzero.numel() == 0:
        return wav
    return wav[:, int(nonzero[0]) : int(nonzero[-1]) + 1]


def drop_trailing_artifact(
    wav: torch.Tensor, sample_rate: int, min_gap_ms: float = 250.0, floor_ratio: float = 0.08
) -> torch.Tensor:
    """
    Cut the hallucinated tail XTTS appends to very short prompts.

    Given one or two characters of Chinese, the model frequently emits the syllable, goes quiet for half a
    second, then produces a breath or a repeat of the syllable. The silence trim above doesn't catch it,
    because the tail is real audio -- it only strips the outer edges. So instead look for a long near-silent
    gap and drop everything after it.

    The gap has to be much longer than a pause inside real speech, hence min_gap_ms. Callers still gate
    this on syllable count, because a long phrase can legitimately hold a pause that long.
    """
    frame = max(1, int(sample_rate * 0.01))
    mono = wav.abs().max(dim=0).values
    frames = mono[: (mono.shape[0] // frame) * frame].reshape(-1, frame).max(dim=1).values
    if frames.numel() == 0:
        return wav

    floor = frames.max() * floor_ratio
    loud = frames > floor
    if not bool(loud.any()):
        return wav

    min_gap_frames = max(1, int(min_gap_ms / 10))
    first_loud = int(torch.nonzero(loud, as_tuple=False)[0])
    gap_start, run = None, 0
    for i in range(first_loud, frames.numel()):
        if loud[i]:
            # Content after a long enough gap is the artifact -- cut back to where the gap began.
            if gap_start is not None and run >= min_gap_frames:
                return wav[:, : gap_start * frame]
            gap_start, run = None, 0
        else:
            if gap_start is None:
                gap_start = i
            run += 1
    return wav


def pick_best_candidate(candidates: list, syllables: int, min_ms_per_syllable: float) -> tuple:
    """
    Choose between repeated generations of the same phrase, shortest first.

    Every way XTTS goes wrong on a short Chinese prompt makes the clip longer than it should be: leading
    noise before the onset, a decaying tail that the silence trim can't reach, or the syllable spoken
    twice. A correct rendition is therefore reliably the shortest of a handful of tries. The floor stops
    that preference from selecting a generation that came out truncated instead.
    """
    if len(candidates) == 1 or not syllables:
        return candidates[0]

    def duration_ms(candidate):
        _, wav, sample_rate = candidate
        return wav.shape[1] * 1000.0 / sample_rate

    floor = min_ms_per_syllable * syllables
    plausible = [c for c in candidates if duration_ms(c) >= floor]
    # Everything came out short -- prefer the longest, which is the least likely to be cut off.
    return min(plausible, key=duration_ms) if plausible else max(candidates, key=duration_ms)


def apply_audio_effects(
    wav: torch.Tensor, sample_rate: int, preset: str = "radio", trim_artifact: bool = False
) -> tuple:
    """
    torchaudio reimplementation of the sox chain in generate_voice_pack.py:
    EQ, overdrive, silence trim both ends, normalise to -1 dBFS, mono, 22050Hz.
    """
    bands, overdrive = EQ_PRESETS[preset]

    if trim_artifact:
        # Before EQ, while the dynamics are still the model's own.
        wav = drop_trailing_artifact(wav, sample_rate)

    for freq, gain_db, q in bands:
        wav = AF.equalizer_biquad(wav, sample_rate, freq, gain_db, q)

    if overdrive is not None:
        wav = AF.overdrive(wav, gain=overdrive[0], colour=overdrive[1])

    # sox trims the head at 0.1% of full scale and the tail at 0.3%
    wav = trim_silence(wav, threshold=0.001)
    wav = torch.flip(trim_silence(torch.flip(wav, [1]), threshold=0.003), [1])

    # mono
    if wav.shape[0] > 1:
        wav = wav.mean(dim=0, keepdim=True)

    # Resample BEFORE normalising. Band-limited interpolation overshoots on
    # transients, so normalising first lets the resampler push peaks back above
    # the target, which then clips on the 16-bit write.
    if sample_rate != TARGET_SAMPLE_RATE:
        wav = AF.resample(wav, sample_rate, TARGET_SAMPLE_RATE)

    # sox `norm -1`: peak at -1 dBFS
    peak = wav.abs().max()
    if peak > 0:
        wav = wav * (10 ** (-1 / 20) / peak)

    return wav, TARGET_SAMPLE_RATE


def save_wav(path: str, wav: torch.Tensor, sample_rate: int) -> None:
    """Write 16-bit PCM, which is what the rest of the CrewChief sound pack uses."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torchaudio.save(
        path, wav.cpu(), sample_rate, encoding="PCM_S", bits_per_sample=16
    )


def main():
    args = parse_arguments()
    device = resolve_device(args.device)

    reference_wavs = sorted(glob.glob(os.path.join(args.baseline_audio_dir, "*.wav")))
    if not reference_wavs:
        raise FileNotFoundError(
            f"No baseline .wav files found in {args.baseline_audio_dir}"
        )
    logging.info(f"Cloning from {len(reference_wavs)} baseline clips")

    with open(args.phrase_inventory, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    logging.info(f"{len(rows)} phrases to generate in language '{args.language}'")

    model = load_model(device)

    logging.info("Computing speaker latents...")
    gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(
        audio_path=reference_wavs
    )

    voicepack_dir = os.path.join(args.output_audio_dir, args.voice_name)
    subtitles: dict = {}
    started = time.time()

    for idx, row in enumerate(rows, 1):
        text = row["text_for_tts"].replace("YOUR_NAME", args.your_name)
        subtitle = row["subtitle"].replace("YOUR_NAME", args.your_name)
        rel_path = row["audio_path"].replace("\\", "/").strip("/")
        filename = row["audio_filename"]

        logging.info(f"[{idx}/{len(rows)}] {rel_path}/{filename}  <-  {text}")

        syllables = sum(1 for ch in text if "一" <= ch <= "鿿")
        # Only short utterances get the artifact trim: a long phrase can hold a real pause as long as
        # the gap the trim looks for.
        trim_artifact = 0 < syllables <= args.artifact_trim_max_syllables
        attempts = (
            args.attempts
            if syllables and (args.attempts_max_syllables == 0 or syllables <= args.attempts_max_syllables)
            else 1
        )

        candidates = []
        for attempt in range(attempts):
            with torch.no_grad():
                out = model.inference(
                    text,
                    args.language,
                    gpt_cond_latent,
                    speaker_embedding,
                    temperature=0.3,
                    top_k=50,
                    top_p=0.8,
                    speed=args.xtts_speed,
                    length_penalty=1.0,
                    repetition_penalty=4.0,
                    enable_text_splitting=False,
                )
            raw = torch.tensor(out["wav"]).unsqueeze(0)
            if args.disable_audio_effects:
                candidates.append((raw, raw, 24000))
            else:
                processed, sr = apply_audio_effects(raw, 24000, args.eq_preset, trim_artifact)
                candidates.append((raw, processed, sr))

        raw, wav, sample_rate = pick_best_candidate(candidates, syllables, args.min_ms_per_syllable)

        out_path = os.path.join(voicepack_dir, rel_path, filename)
        if args.keep_raw:
            save_wav(out_path.replace(".wav", ".raw.wav"), raw, 24000)
        save_wav(out_path, wav, sample_rate)

        duration = torchaudio.info(out_path).num_frames / TARGET_SAMPLE_RATE
        logging.info(f"    -> {duration:.2f}s" + (f" (best of {attempts})" if attempts > 1 else ""))

        subtitles.setdefault(os.path.join(voicepack_dir, rel_path), []).append(
            (filename, subtitle)
        )

    # CrewChief reads one subtitles.csv per phrase folder
    for folder, entries in subtitles.items():
        with open(
            os.path.join(folder, "subtitles.csv"), "w", encoding="utf-8"
        ) as f:
            for filename, subtitle in entries:
                f.write(f'{filename},"{subtitle}"\n')

    elapsed = time.time() - started
    logging.info(
        f"Done: {len(rows)} clips in {elapsed:.0f}s "
        f"({elapsed / max(len(rows), 1):.1f}s per clip) -> {voicepack_dir}"
    )


if __name__ == "__main__":
    main()
