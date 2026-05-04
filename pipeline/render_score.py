"""
render_score.py — Export full movement WAV from MuseScore CLI.
Usage: python render_score.py --mscz <path> --out <wav_path>
"""
import argparse
import subprocess
import sys
from pathlib import Path

MUSESCORE = Path(r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe")


def render_score(mscz_path: Path, out_wav: Path) -> None:
    if not MUSESCORE.exists():
        sys.exit(f"FAIL — MuseScore not found: {MUSESCORE}")
    if not mscz_path.exists():
        sys.exit(f"FAIL — Score file not found: {mscz_path}")

    out_wav.parent.mkdir(parents=True, exist_ok=True)

    cmd = [str(MUSESCORE), "-o", str(out_wav), str(mscz_path)]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout.strip():
        print(f"stdout: {result.stdout.strip()}")
    if result.stderr.strip():
        print(f"stderr: {result.stderr.strip()}")

    if not out_wav.exists():
        sys.exit(f"FAIL — output file not created: {out_wav}")

    size = out_wav.stat().st_size
    if size < 100_000:
        sys.exit(f"FAIL — output suspiciously small ({size} bytes): {out_wav}")

    print(f"OK — {out_wav.name}  ({size:,} bytes / {size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Render score to WAV via MuseScore CLI")
    p.add_argument("--mscz", required=True, help="Path to .mscz file")
    p.add_argument("--out", required=True, help="Output WAV path")
    args = p.parse_args()
    render_score(Path(args.mscz), Path(args.out))
