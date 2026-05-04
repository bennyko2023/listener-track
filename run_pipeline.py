"""
run_pipeline.py — Master script: runs all steps in sequence for one movement.

Usage:
  python run_pipeline.py --cues cues_mv1.json --mscz IMSLP22095.mvt1.mscz \
                         --mxl IMSLP22095.mvt1.mxl --movement 1

  --skip-render   Skip step 1 if the WAV already exists at the correct output path.
"""
import argparse
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
    cmd = [sys.executable, str(script)] + extra_args
    result = subprocess.run(cmd)
    elapsed = time.time() - t0
    if result.returncode != 0:
        sys.exit(f"\nPIPELINE FAILED at: {name}  (exit {result.returncode})")
    print(f"[{name}] completed in {elapsed:.1f}s")


def main() -> None:
    p = argparse.ArgumentParser(description="Run full listener-track pipeline for one movement")
    p.add_argument("--cues", required=True, help="Cues JSON filename  (looked up in cues/)")
    p.add_argument("--mscz", required=True, help="Score filename      (looked up in score/mscz/)")
    p.add_argument("--mxl", required=True, help="MXL filename        (looked up in score/mxl/)")
    p.add_argument("--movement", required=True, type=int)
    p.add_argument("--skip-render", action="store_true",
                   help="Skip step 1 if WAV already exists at output/mv{N}/wav/")
    args = p.parse_args()

    mv = args.movement
    mv_prefix = f"mv{mv}"

    # ── Resolve inputs ────────────────────────────────────────────────────────
    cues_path = BASE_DIR / "cues" / args.cues
    mscz_path = SCORE_DIR / "mscz" / args.mscz
    mxl_path = SCORE_DIR / "mxl" / args.mxl

    for path, flag in [(cues_path, "--cues"), (mscz_path, "--mscz"), (mxl_path, "--mxl")]:
        if not path.exists():
            sys.exit(f"Input not found ({flag}): {path}")

    for path, label in [(KOKORO_MODEL, "kokoro model"), (KOKORO_VOICES, "kokoro voices")]:
        if not path.exists():
            sys.exit(f"Kokoro file not found ({label}): {path}")

    # ── Output paths ──────────────────────────────────────────────────────────
    out_mv = BASE_DIR / "output" / mv_prefix
    wav_path = out_mv / "wav" / f"{mv_prefix}_full.wav"
    tempo_map_path = out_mv / "tempo_map.json"
    clips_dir = out_mv / "clips"
    vo_dir = out_mv / "vo"
    assembled_dir = out_mv / "assembled"
    bumper_path = BASE_DIR / "output" / "bumper.mp3"
    final_path = out_mv / f"{mv_prefix}_commentary.mp3"

    scripts = BASE_DIR / "pipeline"

    print(f"\nPIPELINE — Movement {mv}")
    print(f"  Cues  : {cues_path}")
    print(f"  Score : {mscz_path}")
    print(f"  MXL   : {mxl_path}")
    print(f"  Output: {final_path}")

    t_pipeline = time.time()

    # ── Step 1: Render score → WAV ─────────────────────────────────────────
    if args.skip_render and wav_path.exists():
        print(f"\nSKIP step 1 — WAV exists: {wav_path}")
    else:
        run_step("render_score", scripts / "render_score.py", [
            "--mscz", str(mscz_path),
            "--out", str(wav_path),
        ])

    # ── Step 2: Build tempo map ────────────────────────────────────────────
    run_step("build_tempo_map", scripts / "build_tempo_map.py", [
        "--mxl", str(mxl_path),
        "--wav", str(wav_path),
        "--out", str(tempo_map_path),
    ])

    # ── Step 3: Extract clips ──────────────────────────────────────────────
    run_step("extract_clips", scripts / "extract_clips.py", [
        "--cues", str(cues_path),
        "--tempo-map", str(tempo_map_path),
        "--wav", str(wav_path),
        "--out-dir", str(clips_dir),
    ])

    # ── Step 4: Generate VO ────────────────────────────────────────────────
    run_step("generate_vo", scripts / "generate_vo.py", [
        "--cues", str(cues_path),
        "--out-dir", str(vo_dir),
        "--model", str(KOKORO_MODEL),
        "--voices", str(KOKORO_VOICES),
    ])

    # ── Step 5: Assemble cues ──────────────────────────────────────────────
    run_step("assemble_cues", scripts / "assemble_cues.py", [
        "--cues", str(cues_path),
        "--vo-dir", str(vo_dir),
        "--clips-dir", str(clips_dir),
        "--out-dir", str(assembled_dir),
    ])

    # ── Step 6: Concatenate movement ───────────────────────────────────────
    run_step("concat_movement", scripts / "concat_movement.py", [
        "--cues", str(cues_path),
        "--assembled-dir", str(assembled_dir),
        "--vo-dir", str(vo_dir),
        "--bumper", str(bumper_path),
        "--out", str(final_path),
    ])

    elapsed = time.time() - t_pipeline
    print(f"\n{'=' * 64}")
    print(f"  PIPELINE COMPLETE — Movement {mv}")
    print(f"  Output : {final_path}")
    print(f"  Total  : {elapsed:.1f}s  ({elapsed / 60:.1f} min)")
    print(f"{'=' * 64}\n")


if __name__ == "__main__":
    main()
