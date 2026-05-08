"""
run_teaser.py — Teaser pipeline: assembles cross-movement promotional MP3.

Usage:
  python run_teaser.py [--cues cues_teaser.json] [--mxl-dir <dir>]
                       [--output output/teaser/teaser.mp3] [--no-cache]

Requires per-movement WAVs at output/mv{N}/wav/mv{N}_full.wav.
Run run_pipeline.py for each source movement first if they don't exist.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
SCORE_DIR = Path(r"C:\data\beethoven\serioso\score")
KOKORO_MODEL = BASE_DIR / "kokoro-v1.0.onnx"
KOKORO_VOICES = BASE_DIR / "voices-v1.0.bin"


def run_step(name: str, script: Path, extra_args: list) -> None:
    print(f"\n{'=' * 64}")
    print(f"  STEP: {name}")
    print(f"{'=' * 64}")
    t0 = time.time()
    result = subprocess.run([sys.executable, str(script)] + extra_args)
    elapsed = time.time() - t0
    if result.returncode != 0:
        sys.exit(f"\nPIPELINE FAILED at: {name}  (exit {result.returncode})")
    print(f"[{name}] completed in {elapsed:.1f}s")


def main() -> None:
    p = argparse.ArgumentParser(description="Run teaser pipeline (cross-movement promotional MP3)")
    p.add_argument("--cues", default="cues_teaser.json", help="Teaser cues JSON filename (in cues/)")
    p.add_argument("--mxl-dir", default=str(SCORE_DIR / "mxl"), help="Directory containing MXL files")
    p.add_argument("--output", default="output/teaser/teaser.mp3", help="Output MP3 path")
    p.add_argument("--no-cache", action="store_true", help="Re-render all clips and VO even if cached")
    args = p.parse_args()

    cues_path = BASE_DIR / "cues" / args.cues
    mxl_dir = Path(args.mxl_dir)
    out_arg = Path(args.output)
    output_path = out_arg if out_arg.is_absolute() else BASE_DIR / out_arg

    for path, label in [
        (cues_path, "--cues"),
        (mxl_dir, "--mxl-dir"),
        (KOKORO_MODEL, "kokoro model"),
        (KOKORO_VOICES, "kokoro voices"),
    ]:
        if not path.exists():
            sys.exit(f"Input not found ({label}): {path}")

    out_teaser = output_path.parent
    clips_dir = out_teaser / "clips"
    vo_dir = out_teaser / "vo"
    silences_dir = out_teaser / "silences"
    bumper_path = BASE_DIR / "output" / "bumper.mp3"
    scripts = BASE_DIR / "pipeline"

    print("\nTEASER PIPELINE")
    print(f"  Cues   : {cues_path}")
    print(f"  MXL dir: {mxl_dir}")
    print(f"  Output : {output_path}")

    t_pipeline = time.time()

    # ── Step 1: Extract clips (multi-source movement routing) ────────────────
    step1_args = [
        "--cues", str(cues_path),
        "--mxl-dir", str(mxl_dir),
        "--out-dir", str(clips_dir),
    ]
    if args.no_cache:
        step1_args.append("--no-cache")
    run_step("teaser_extract_clips", scripts / "teaser_extract_clips.py", step1_args)

    # ── Step 2: Generate VO (reuses generate_vo.py unchanged) ────────────────
    run_step("generate_vo", scripts / "generate_vo.py", [
        "--cues", str(cues_path),
        "--out-dir", str(vo_dir),
        "--model", str(KOKORO_MODEL),
        "--voices", str(KOKORO_VOICES),
    ])

    # ── Step 3: Assemble final teaser MP3 ─────────────────────────────────────
    # Done directly (not via subprocess) to control the exact assembly order:
    # bumper → intro → [for each cue: (between_sil if i>0) + vo_pre + pre_sil
    #                   + clip + post_sil + vo_post] → outro_sil → outro
    # This ensures no trailing silence_between after the last cue.
    print(f"\n{'=' * 64}")
    print("  STEP: assemble_teaser")
    print(f"{'=' * 64}")
    t0 = time.time()

    sys.path.insert(0, str(BASE_DIR))
    from pipeline.assemble_cues import concat_files, generate_silence
    from pipeline.concat_movement import get_duration

    with open(cues_path) as f:
        cues_data = json.load(f)

    silences_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def sil(ms: int) -> Path:
        path = silences_dir / f"silence_{ms}ms.mp3"
        generate_silence(ms / 1000.0, path)
        return path

    bumper_data = cues_data.get("bumper", {})
    intro_data = cues_data.get("intro", {})
    outro_data = cues_data.get("outro", {})
    mv_prefix = f"mv{cues_data['movement']}"  # "mv0" for teaser

    intro_path = vo_dir / f"{mv_prefix}_intro.mp3"
    outro_path = vo_dir / f"{mv_prefix}_outro.mp3"
    pre_ms = int(cues_data.get("silence_pre_clip_ms", 500))
    post_ms = int(cues_data.get("silence_post_clip_ms", 1000))
    between_ms = int(cues_data.get("silence_between_cues_ms", 1500))

    required = [
        (bumper_path, "bumper"),
        (intro_path, "intro VO"),
        (outro_path, "outro VO"),
    ]
    for cue in cues_data["cues"]:
        cid = cue["cue_id"]
        required += [
            (vo_dir / f"{cid}_vo_pre.mp3", f"{cid} vo_pre"),
            (clips_dir / f"{cid}_clip.mp3", f"{cid} clip"),
            (vo_dir / f"{cid}_vo_post.mp3", f"{cid} vo_post"),
        ]
    for path, label in required:
        if not path.exists():
            sys.exit(f"FAIL — missing: {path}  ({label})")

    files = [
        bumper_path,
        sil(bumper_data.get("silence_after_ms", 1000)),
        intro_path,
        sil(intro_data.get("silence_after_ms", 1500)),
    ]
    for i, cue in enumerate(cues_data["cues"]):
        cid = cue["cue_id"]
        if i > 0:
            files.append(sil(between_ms))
        files += [
            vo_dir / f"{cid}_vo_pre.mp3",
            sil(pre_ms),
            clips_dir / f"{cid}_clip.mp3",
            sil(post_ms),
            vo_dir / f"{cid}_vo_post.mp3",
        ]
    files += [
        sil(outro_data.get("silence_before_ms", 2000)),
        outro_path,
    ]

    print(f"Concatenating {len(files)} segments ...")
    concat_files(files, output_path)

    duration = get_duration(output_path)
    size = output_path.stat().st_size
    elapsed = time.time() - t0
    print(f"OK — {output_path.name}")
    print(f"     Duration : {duration:.1f}s  ({duration / 60:.1f} min)")
    print(f"     File size: {size:,} bytes  ({size / 1_048_576:.1f} MB)")
    print(f"[assemble_teaser] completed in {elapsed:.1f}s")

    elapsed_total = time.time() - t_pipeline
    print(f"\n{'=' * 64}")
    print("  TEASER PIPELINE COMPLETE")
    print(f"  Output : {output_path}")
    print(f"  Total  : {elapsed_total:.1f}s  ({elapsed_total / 60:.1f} min)")
    print(f"{'=' * 64}\n")


if __name__ == "__main__":
    main()
