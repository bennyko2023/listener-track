"""
assemble_cues.py — Assemble each cue as: vo_pre + silence + clip + silence + vo_post + silence.
Usage: python assemble_cues.py --cues <json> --vo-dir <dir> --clips-dir <dir> --out-dir <dir>
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


def concat_files(file_list: list, out_path: Path) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        for fp in file_list:
            f.write(f"file '{Path(fp).as_posix()}'\n")
        list_path = Path(f.name)

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
        sys.exit(f"FAIL — concat failed for {out_path.name}")


def assemble_cues(
    cues_path: Path,
    vo_dir: Path,
    clips_dir: Path,
    out_dir: Path,
) -> None:
    with open(cues_path) as f:
        cues_data = json.load(f)

    silence_pre_s = cues_data.get("silence_pre_clip_ms", 500) / 1000.0
    silence_post_s = cues_data.get("silence_post_clip_ms", 1000) / 1000.0
    silence_between_s = cues_data.get("silence_between_cues_ms", 1500) / 1000.0

    out_dir.mkdir(parents=True, exist_ok=True)
    silences_dir = out_dir.parent / "silences"
    silences_dir.mkdir(exist_ok=True)

    # Generate required silence files once
    silence_files = {}
    for ms in {
        int(silence_pre_s * 1000),
        int(silence_post_s * 1000),
        int(silence_between_s * 1000),
    }:
        path = silences_dir / f"silence_{ms}ms.mp3"
        generate_silence(ms / 1000.0, path)
        silence_files[ms] = path

    def sil(ms: int) -> Path:
        return silence_files[ms]

    for cue in cues_data["cues"]:
        cue_id = cue["cue_id"]
        out_path = out_dir / f"{cue_id}.mp3"

        vo_pre = vo_dir / f"{cue_id}_vo_pre.mp3"
        vo_post = vo_dir / f"{cue_id}_vo_post.mp3"
        clip = clips_dir / f"{cue_id}_clip.mp3"

        for p in (vo_pre, clip, vo_post):
            if not p.exists():
                sys.exit(f"FAIL — required file missing: {p}")

        files = [
            vo_pre,
            sil(int(silence_pre_s * 1000)),
            clip,
            sil(int(silence_post_s * 1000)),
            vo_post,
            sil(int(silence_between_s * 1000)),
        ]

        print(f"Assembling {cue_id} ...")
        concat_files(files, out_path)

    print(f"\nOK — {len(cues_data['cues'])} assembled cues → {out_dir}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Assemble cue segments via FFmpeg concat")
    p.add_argument("--cues", required=True)
    p.add_argument("--vo-dir", required=True)
    p.add_argument("--clips-dir", required=True)
    p.add_argument("--out-dir", required=True)
    args = p.parse_args()
    assemble_cues(
        Path(args.cues),
        Path(args.vo_dir),
        Path(args.clips_dir),
        Path(args.out_dir),
    )
