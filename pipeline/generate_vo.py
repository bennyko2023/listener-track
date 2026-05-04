"""
generate_vo.py — Generate all VO lines via Kokoro TTS and convert to MP3.
Usage: python generate_vo.py --cues <json> --out-dir <vo_dir> --model <onnx> --voices <bin>

Bumper is written to out_dir/../../bumper.mp3 (output root) and skipped if it exists.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def wav_to_mp3(wav_path: Path, mp3_path: Path) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-i", str(wav_path),
        "-ar", "44100", "-ac", "1", "-b:a", "128k",
        str(mp3_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    wav_path.unlink(missing_ok=True)
    if result.returncode != 0:
        sys.exit(f"FAIL — WAV→MP3 conversion failed for {wav_path.name}\n{result.stderr}")


def generate_vo(
    cues_path: Path,
    vo_dir: Path,
    model_path: Path,
    voices_path: Path,
) -> None:
    try:
        import soundfile as sf
        from kokoro_onnx import Kokoro
    except ImportError as e:
        sys.exit(f"Missing dependency: {e}\nRun: pip install kokoro-onnx soundfile")

    with open(cues_path) as f:
        cues_data = json.load(f)

    voice = cues_data.get("voice", "af_sarah")
    speed = cues_data.get("speed", 0.92)
    lang = cues_data.get("lang", "en-us")
    mv = cues_data["movement"]
    mv_prefix = f"mv{mv}"

    print(f"Loading Kokoro model: {model_path.name} ...")
    kokoro = Kokoro(str(model_path), str(voices_path))
    print(f"Ready. Voice={voice}  Speed={speed}  Lang={lang}\n")

    vo_dir.mkdir(parents=True, exist_ok=True)
    # Bumper lives at output/ root (parent of mv1/, mv2/, etc.)
    bumper_dir = vo_dir.parent.parent

    def render(text: str, stem: str, target_dir: Path) -> None:
        mp3_path = target_dir / f"{stem}.mp3"
        if mp3_path.exists():
            print(f"  SKIP  {stem}.mp3 (exists)")
            return
        wav_path = target_dir / f"_{stem}_tmp.wav"
        print(f"  {stem}  ({len(text)} chars)")
        samples, sr = kokoro.create(text, voice=voice, speed=speed, lang=lang)
        sf.write(str(wav_path), samples, sr)
        wav_to_mp3(wav_path, mp3_path)

    bumper_data = cues_data.get("bumper", {})
    if bumper_data.get("vo"):
        print("Bumper:")
        render(bumper_data["vo"], "bumper", bumper_dir)

    intro_data = cues_data.get("intro", {})
    if intro_data.get("vo"):
        print("Intro:")
        render(intro_data["vo"], f"{mv_prefix}_intro", vo_dir)

    for cue in cues_data["cues"]:
        cue_id = cue["cue_id"]
        print(f"Cue {cue_id}:")
        render(cue["vo_pre"], f"{cue_id}_vo_pre", vo_dir)
        render(cue["vo_post"], f"{cue_id}_vo_post", vo_dir)

    outro_data = cues_data.get("outro", {})
    if outro_data.get("vo"):
        print("Outro:")
        render(outro_data["vo"], f"{mv_prefix}_outro", vo_dir)

    total = 2 + 2 * len(cues_data["cues"]) + 2  # bumper, intro, cues×2, outro
    print(f"\nOK — up to {total} VO files → {vo_dir}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate VO files via Kokoro TTS")
    p.add_argument("--cues", required=True)
    p.add_argument("--out-dir", required=True, help="VO output dir (output/mv1/vo)")
    p.add_argument("--model", required=True, help="Path to kokoro-v1.0.onnx")
    p.add_argument("--voices", required=True, help="Path to voices-v1.0.bin")
    args = p.parse_args()
    generate_vo(
        Path(args.cues),
        Path(args.out_dir),
        Path(args.model),
        Path(args.voices),
    )
