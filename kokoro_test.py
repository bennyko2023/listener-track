"""
Op. 95 Listener Track — Kokoro TTS test
Generates 3 VO clips from MV1 cues.

SETUP (run once):
    pip install kokoro-onnx soundfile numpy

DOWNLOAD MODEL FILES (run once):
    wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
    wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

    Or on Windows, download manually from:
    https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0

USAGE:
    python kokoro_test.py

OUTPUT:
    ./output/cue01_vo_pre.wav
    ./output/cue01_vo_post.wav
    ./output/cue02_vo_pre.wav
    ... etc (6 files total, 3 cues x 2 lines each)
"""

import os
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

# ── CONFIG ──────────────────────────────────────────────────────────────────

MODEL_PATH  = "kokoro-v1.0.onnx"   # path to downloaded model
VOICES_PATH = "voices-v1.0.bin"    # path to downloaded voices

VOICE  = "af_sarah"   # options: af_sarah, am_adam, bf_emma, bm_george
SPEED  = 0.92         # slightly slower than default for clarity
LANG   = "en-us"

OUTPUT_DIR = "./output"

# ── CUE SCRIPTS ─────────────────────────────────────────────────────────────
# Three cues from MV1: the opening unison, the dominant suspension, the deceptive cadence.
# Each cue has a pre-clip line and a post-clip line.

CUES = [
    {
        "id": "cue01",
        "label": "m.1 — opening unison",
        "vo_pre": (
            "The quartet opens in unison — all four instruments playing the same "
            "single line, no chords, no harmony. This descending figure moves through "
            "eight notes drawn from F minor, the home key."
        ),
        "vo_post": (
            "That bare unison is not a conventional opening. It collapses the four "
            "voices into one. The quartet begins by denying itself its own texture."
        ),
    },
    {
        "id": "cue02",
        "label": "mm.3–5 — dominant suspension",
        "vo_pre": (
            "The first violin leaps two octaves upward to a high C. "
            "Beneath it, the other three instruments hold a bare open fifth on C — "
            "the dominant, the note of maximum tension in F minor. "
            "The music is suspended, waiting for an answer."
        ),
        "vo_post": (
            "That held sound is unstable by design. In F minor, C is the dominant — "
            "the pitch that demands resolution back to the home key. "
            "The question is where it will land."
        ),
    },
    {
        "id": "cue03",
        "label": "m.6 — deceptive cadence to D-flat major",
        "vo_pre": (
            "Everything in the last few bars pointed toward a landing on F minor. "
            "Listen to where it actually goes."
        ),
        "vo_post": (
            "That was D-flat major — a deceptive cadence. The harmony promised F minor "
            "and delivered something entirely different. "
            "D-flat is not a random detour. It will turn out to be the destination "
            "the entire exposition has been heading toward."
        ),
    },
]

# ── MAIN ────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Loading Kokoro model from {MODEL_PATH} ...")
    kokoro = Kokoro(MODEL_PATH, VOICES_PATH)
    print(f"Model loaded. Voice: {VOICE}, Speed: {SPEED}\n")

    for cue in CUES:
        print(f"Generating {cue['id']} — {cue['label']}")

        for part in ["vo_pre", "vo_post"]:
            text = cue[part]
            char_count = len(text)
            out_path = os.path.join(OUTPUT_DIR, f"{cue['id']}_{part}.wav")

            samples, sample_rate = kokoro.create(
                text,
                voice=VOICE,
                speed=SPEED,
                lang=LANG,
            )

            sf.write(out_path, samples, sample_rate)
            print(f"  [{part}] {char_count} chars → {out_path}")

    print(f"\nDone. {len(CUES) * 2} files written to {OUTPUT_DIR}/")
    print("\nListen to the files and note:")
    print("  - Clarity of technical terms (D-flat, dominant, deceptive cadence)")
    print("  - Pacing — does 0.92 speed feel right?")
    print("  - Voice character — try VOICE='am_adam' for a male alternative")


if __name__ == "__main__":
    main()
