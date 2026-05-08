"""
teaser_extract_clips.py — Extract clips from multiple source movements for the teaser.
Usage: python teaser_extract_clips.py --cues <teaser_json> --mxl-dir <dir> --out-dir <dir> [--no-cache]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def run_ffmpeg(cmd: list, label: str) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg stderr:\n{result.stderr}")
        sys.exit(f"FAIL — FFmpeg error ({label})")


def teaser_extract_clips(
    cues_path: Path,
    mxl_dir: Path,
    out_dir: Path,
    no_cache: bool = False,
) -> None:
    with open(cues_path) as f:
        cues_data = json.load(f)

    mxl_map = {m["mv"]: mxl_dir / m["file"] for m in cues_data["source_movements"]}
    needed_mvs = {cue["movement"] for cue in cues_data["cues"]}

    # Load (or build) tempo maps for each needed movement
    tempo_maps = {}
    for mv in sorted(needed_mvs):
        wav_path = BASE_DIR / "output" / f"mv{mv}" / "wav" / f"mv{mv}_full.wav"
        if not wav_path.exists():
            sys.exit(
                f"FAIL — WAV missing for movement {mv}: {wav_path}\n"
                f"       Run the per-movement pipeline first:\n"
                f"         python run_pipeline.py --movement {mv} --cues cues_mv{mv}.json "
                f"--mscz <file> --mxl <file>"
            )

        tempo_map_path = BASE_DIR / "output" / f"mv{mv}" / "tempo_map.json"
        if not tempo_map_path.exists():
            mxl_path = mxl_map.get(mv)
            if not mxl_path:
                sys.exit(f"FAIL — movement {mv} not listed in source_movements")
            if not mxl_path.exists():
                sys.exit(f"FAIL — MXL not found for movement {mv}: {mxl_path}")
            print(f"Building tempo map for movement {mv} ...")
            result = subprocess.run([
                sys.executable,
                str(Path(__file__).parent / "build_tempo_map.py"),
                "--mxl", str(mxl_path),
                "--wav", str(wav_path),
                "--out", str(tempo_map_path),
            ])
            if result.returncode != 0:
                sys.exit(f"FAIL — build_tempo_map failed for movement {mv}")

        with open(tempo_map_path) as f:
            tempo_maps[mv] = json.load(f)

    fade_in_s = cues_data.get("clip_fade_in_ms", 300) / 1000.0
    fade_out_s = cues_data.get("clip_fade_out_ms", 500) / 1000.0

    out_dir.mkdir(parents=True, exist_ok=True)
    short_clips = []

    for cue in cues_data["cues"]:
        cue_id = cue["cue_id"]
        out_path = out_dir / f"{cue_id}_clip.mp3"

        if out_path.exists() and not no_cache:
            print(f"  SKIP  {cue_id}_clip.mp3 (cached)")
            continue

        mv = cue["movement"]
        tempo_map = tempo_maps[mv]
        wav_path = BASE_DIR / "output" / f"mv{mv}" / "wav" / f"mv{mv}_full.wav"

        if "clip_measures" in cue:
            m_start, m_end = cue["clip_measures"]
        else:
            m_start, m_end = cue["measure_start"], cue["measure_end"]

        key_start = str(m_start)
        key_end = str(m_end + 1)

        if key_start not in tempo_map:
            sys.exit(f"FAIL — measure {m_start} not in mv{mv} tempo map (cue {cue_id})")
        if key_end not in tempo_map:
            sys.exit(f"FAIL — measure {m_end + 1} not in mv{mv} tempo map (cue {cue_id})")

        t_start = float(tempo_map[key_start])
        t_end = float(tempo_map[key_end])

        for rep in tempo_map.get("_repeats", []):
            if t_start < rep["base_end_s"] and t_end > rep["base_end_s"] + rep["extra_s"]:
                t_start += rep["extra_s"]
                break

        duration = t_end - t_start
        if duration < 0.1:
            sys.exit(f"FAIL — invalid clip duration {duration:.3f}s for {cue_id}")

        fade_out_start = max(0.0, duration - fade_out_s)
        afade = (
            f"afade=t=in:st=0:d={fade_in_s},"
            f"afade=t=out:st={fade_out_start:.4f}:d={fade_out_s}"
        )

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(t_start),
            "-i", str(wav_path),
            "-t", str(duration),
            "-af", afade,
            "-ar", "44100", "-ac", "1", "-b:a", "128k",
            str(out_path),
        ]

        print(f"{cue_id} [mv{mv}]: m{m_start}–m{m_end}  {t_start:.3f}s–{t_end:.3f}s  ({duration:.2f}s)")
        run_ffmpeg(cmd, cue_id)

        if duration < 5.0:
            short_clips.append((cue_id, duration))

    print(f"\nOK — {len(cues_data['cues'])} clips → {out_dir}")
    if short_clips:
        print(f"\nWARNING — {len(short_clips)} clips under 5s (possible tempo map error):")
        for cid, dur in short_clips:
            print(f"  {cid}: {dur:.2f}s")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Extract teaser clips from multiple source movements")
    p.add_argument("--cues", required=True, help="Path to cues_teaser.json")
    p.add_argument("--mxl-dir", required=True, help="Directory containing MXL files")
    p.add_argument("--out-dir", required=True, help="Output directory for clips")
    p.add_argument("--no-cache", action="store_true", help="Re-extract even if clip exists")
    args = p.parse_args()
    teaser_extract_clips(
        Path(args.cues),
        Path(args.mxl_dir),
        Path(args.out_dir),
        no_cache=args.no_cache,
    )
