"""
concat_movement.py — Concatenate all segments into final movement commentary MP3.
Usage: python concat_movement.py --cues <json> --assembled-dir <dir> --vo-dir <dir>
                                  --bumper <path> --out <path>
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def generate_silence(duration_s: float, out_path: Path) -> None:
    if out_path.exists():
        return
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(duration_s),
        "-acodec", "libmp3lame", "-b:a", "128k",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"FAIL — silence generation failed:\n{result.stderr}")


def get_duration(path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def concat_movement(
    cues_path: Path,
    assembled_dir: Path,
    vo_dir: Path,
    bumper_path: Path,
    out_path: Path,
) -> None:
    with open(cues_path) as f:
        cues_data = json.load(f)

    mv = cues_data["movement"]
    mv_prefix = f"mv{mv}"

    silences_dir = out_path.parent / "silences"
    silences_dir.mkdir(exist_ok=True)

    def silence(ms: int) -> Path:
        path = silences_dir / f"silence_{ms}ms.mp3"
        generate_silence(ms / 1000.0, path)
        return path

    files = []

    def require(path: Path, label: str) -> None:
        if not path.exists():
            sys.exit(f"FAIL — missing: {path}  ({label})")
        files.append(path)

    # Bumper
    require(bumper_path, "bumper")
    files.append(silence(cues_data.get("bumper", {}).get("silence_after_ms", 1000)))

    # Intro
    intro_path = vo_dir / f"{mv_prefix}_intro.mp3"
    require(intro_path, "intro")
    files.append(silence(cues_data.get("intro", {}).get("silence_after_ms", 1500)))

    # Assembled cues (each already contains trailing silence_between_cues)
    for cue in cues_data["cues"]:
        cue_path = assembled_dir / f"{cue['cue_id']}.mp3"
        require(cue_path, cue["cue_id"])

    # Outro silence then outro
    files.append(silence(cues_data.get("outro", {}).get("silence_before_ms", 2000)))
    outro_path = vo_dir / f"{mv_prefix}_outro.mp3"
    require(outro_path, "outro")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        for fp in files:
            f.write(f"file '{Path(fp).as_posix()}'\n")
        list_path = Path(f.name)

    print(f"Concatenating {len(files)} segments ...")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_path),
        "-acodec", "libmp3lame", "-b:a", "128k",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    list_path.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"FFmpeg stderr:\n{result.stderr}")
        sys.exit("FAIL — final concat failed")

    duration = get_duration(out_path)
    size = out_path.stat().st_size
    print(f"OK — {out_path.name}")
    print(f"     Duration : {duration:.1f}s  ({duration / 60:.1f} min)")
    print(f"     File size: {size:,} bytes  ({size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Concatenate movement segments into final MP3")
    p.add_argument("--cues", required=True)
    p.add_argument("--assembled-dir", required=True)
    p.add_argument("--vo-dir", required=True)
    p.add_argument("--bumper", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    concat_movement(
        Path(args.cues),
        Path(args.assembled_dir),
        Path(args.vo_dir),
        Path(args.bumper),
        Path(args.out),
    )
