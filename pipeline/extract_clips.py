"""
extract_clips.py — Cut measure-range clips from full WAV using FFmpeg.
Usage: python extract_clips.py --cues <json> --tempo-map <json> --wav <wav> --out-dir <dir>
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_ffmpeg(cmd: list, label: str) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg stderr:\n{result.stderr}")
        sys.exit(f"FAIL — FFmpeg error ({label})")


def extract_clips(
    cues_path: Path,
    tempo_map_path: Path,
    wav_path: Path,
    out_dir: Path,
) -> None:
    with open(cues_path) as f:
        cues_data = json.load(f)
    with open(tempo_map_path) as f:
        tempo_map = json.load(f)

    repeats = tempo_map.get("_repeats", [])

    fade_in_s = cues_data.get("clip_fade_in_ms", 300) / 1000.0
    fade_out_s = cues_data.get("clip_fade_out_ms", 500) / 1000.0

    out_dir.mkdir(parents=True, exist_ok=True)

    short_clips = []

    for cue in cues_data["cues"]:
        cue_id = cue.get("cue_id", "<unknown>")
        if "clip_measures" in cue:
            m_start, m_end = cue["clip_measures"]
        elif "measure_start" in cue and "measure_end" in cue:
            m_start, m_end = cue["measure_start"], cue["measure_end"]
        else:
            sys.exit(f"FAIL — cue '{cue_id}' has neither clip_measures nor measure_start/measure_end")

        key_start = str(m_start)
        key_end = str(m_end + 1)

        if key_start not in tempo_map:
            sys.exit(f"FAIL — measure {m_start} not in tempo map (cue {cue_id})")
        if key_end not in tempo_map:
            sys.exit(f"FAIL — measure {m_end + 1} not in tempo map (cue {cue_id})")

        t_start = tempo_map[key_start]
        t_end = tempo_map[key_end]

        # If this clip spans a repeat boundary (start is in the first pass,
        # end is after the repeat resolves), shift t_start to the second-pass
        # occurrence so the repeat is not included in the extracted clip.
        for rep in repeats:
            if t_start < rep["base_end_s"] and t_end > rep["base_end_s"] + rep["extra_s"]:
                t_start += rep["extra_s"]
                break

        duration = t_end - t_start

        if duration < 0.1:
            sys.exit(f"FAIL — invalid clip duration {duration:.3f}s for {cue_id}")

        # Clamp fade_out start so it never goes negative on very short clips
        fade_out_start = max(0.0, duration - fade_out_s)

        afade = (
            f"afade=t=in:st=0:d={fade_in_s},"
            f"afade=t=out:st={fade_out_start:.4f}:d={fade_out_s}"
        )

        out_path = out_dir / f"{cue_id}_clip.mp3"

        # -ss before -i for fast input seeking (accurate enough for WAV)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(t_start),
            "-i", str(wav_path),
            "-t", str(duration),
            "-af", afade,
            "-ar", "44100",
            "-ac", "1",
            "-b:a", "128k",
            str(out_path),
        ]

        print(f"{cue_id}: m{m_start}–m{m_end}  {t_start:.3f}s – {t_end:.3f}s  ({duration:.2f}s)")
        run_ffmpeg(cmd, cue_id)

        if duration < 5.0:
            short_clips.append((cue_id, duration))

    print(f"\nOK — {len(cues_data['cues'])} clips → {out_dir}")
    if short_clips:
        print(f"\nWARNING — {len(short_clips)} clips under 5s (possible tempo map error):")
        for cid, dur in short_clips:
            print(f"  {cid}: {dur:.2f}s")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Extract measure clips from WAV via FFmpeg")
    p.add_argument("--cues", required=True)
    p.add_argument("--tempo-map", required=True)
    p.add_argument("--wav", required=True)
    p.add_argument("--out-dir", required=True)
    args = p.parse_args()
    extract_clips(
        Path(args.cues),
        Path(args.tempo_map),
        Path(args.wav),
        Path(args.out_dir),
    )
