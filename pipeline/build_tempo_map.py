"""
build_tempo_map.py — Extract measure-to-timestamp lookup from MXL score.
Usage: python build_tempo_map.py --mxl <path> --wav <wav_path> --out <json_path>
"""
import argparse
import json
import sys
from pathlib import Path


def detect_leading_silence(wav_path: Path, threshold_db: float = -50.0) -> float:
    """Return seconds of leading silence before the first non-silent frame."""
    import numpy as np

    try:
        import librosa
        y, sr = librosa.load(str(wav_path), sr=None, mono=True)
    except ImportError:
        try:
            import soundfile as sf
            y, sr = sf.read(str(wav_path), always_2d=False)
            if y.ndim > 1:
                y = y.mean(axis=1)
        except Exception as e:
            print(f"Warning: could not load WAV for silence detection: {e}")
            return 0.0

    threshold_amp = 10 ** (threshold_db / 20.0)
    non_silent = np.where(np.abs(y) > threshold_amp)[0]
    if len(non_silent) == 0:
        return 0.0
    return float(non_silent[0]) / sr


def compute_time_at_offset(target_ql: float, segments: list) -> float:
    """Convert a quarterLength offset to real-time seconds using tempo segments."""
    time = 0.0
    for start_ql, end_ql, bpm in segments:
        if start_ql >= target_ql:
            break
        seg_end = min(end_ql, target_ql)
        time += (seg_end - start_ql) * (60.0 / bpm)
    return time


def build_tempo_map(mxl_path: Path, wav_path: Path, out_path: Path) -> None:
    try:
        import music21
        from music21 import tempo as m21tempo
    except ImportError:
        sys.exit("music21 not installed. Run: pip install music21")

    print(f"Parsing: {mxl_path.name}")
    score = music21.converter.parse(str(mxl_path))

    # Extract all tempo markings (offset is in quarterLengths from score start)
    tempos = []
    for element in score.flatten().getElementsByClass(m21tempo.MetronomeMark):
        if element.number:
            tempos.append((float(element.offset), float(element.number)))

    if not tempos:
        print("No MetronomeMark found — defaulting to quarter=120")
        tempos = [(0.0, 120.0)]
    else:
        tempos.sort()
        if tempos[0][0] > 0.0:
            tempos.insert(0, (0.0, 120.0))
        print(f"Tempo markings (offset_ql, bpm): {tempos}")

    # Build tempo segments: (start_ql, end_ql, bpm)
    segments = []
    for i, (offset, bpm) in enumerate(tempos):
        end = tempos[i + 1][0] if i + 1 < len(tempos) else float("inf")
        segments.append((offset, end, bpm))

    # Get measures from first part (violin I — all parts share the same measure grid)
    parts = list(score.parts)
    if not parts:
        sys.exit("FAIL — no parts found in score")

    part = parts[0]
    measures = sorted(part.getElementsByClass("Measure"), key=lambda m: m.offset)
    if not measures:
        sys.exit("FAIL — no measures found in first part")

    print(f"Measures found: {len(measures)}")

    # Build map: str(measure_number) -> seconds from score start
    tempo_map = {}
    for m in measures:
        mn = str(m.number)
        t = compute_time_at_offset(float(m.offset), segments)
        tempo_map[mn] = round(t, 4)

    # Sentinel: start of (last_measure_number + 1) = end of last measure
    last_m = measures[-1]
    last_end_ql = float(last_m.offset) + float(last_m.quarterLength)
    tempo_map[str(last_m.number + 1)] = round(
        compute_time_at_offset(last_end_ql, segments), 4
    )

    # Apply leading silence offset from WAV
    if wav_path and wav_path.exists():
        print(f"Detecting leading silence in {wav_path.name} ...")
        silence_s = detect_leading_silence(wav_path)
        print(f"Leading silence: {silence_s:.4f}s")
        if silence_s > 0.0:
            for k in tempo_map:
                tempo_map[k] = round(tempo_map[k] + silence_s, 4)
    else:
        print("WAV not available — skipping silence detection")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(tempo_map, f, indent=2)

    entries = list(tempo_map.items())
    print(f"OK — {len(tempo_map)} entries → {out_path}")
    print(f"First 6: {dict(entries[:6])}")
    print(f"Last entry: {dict(entries[-1:])}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Build measure-to-timestamp map from MXL")
    p.add_argument("--mxl", required=True, help="Path to .mxl file")
    p.add_argument("--wav", required=True, help="Rendered WAV for leading silence detection")
    p.add_argument("--out", required=True, help="Output JSON path")
    args = p.parse_args()
    build_tempo_map(Path(args.mxl), Path(args.wav), Path(args.out))
