# Beethoven Op. 95 "Serioso" — Listener Track Pipeline

Automated pipeline that generates a guided listening commentary MP3 for each movement of Beethoven's String Quartet Op. 95.

## What it produces

```
bumper → intro → [vo_pre → clip → vo_post] × N cues → outro
```

One MP3 per movement, assembled from Kokoro TTS voice-over and measure-range clips extracted from a MuseScore render.

---

## Dependencies

```powershell
pip install music21 kokoro-onnx soundfile numpy pydub librosa
```

Also required (must be on PATH or at expected paths):
- [FFmpeg](https://ffmpeg.org/) — `C:\ffmpeg\bin\ffmpeg.exe`
- [MuseScore 4](https://musescore.org/) — `C:\Program Files\MuseScore 4\bin\MuseScore4.exe`
- Kokoro model files in the project root: `kokoro-v1.0.onnx`, `voices-v1.0.bin`

---

## Directory structure

```
listener-track/
  run_pipeline.py          # entry point
  cues/
    cues_mv1.json          # cue definitions per movement
  pipeline/
    render_score.py        # Step 1: render score to WAV via MuseScore
    build_tempo_map.py     # Step 2: extract measure timestamps from MXL
    extract_clips.py       # Step 3: cut measure-range clips via FFmpeg
    generate_vo.py         # Step 4: generate voice-over via Kokoro TTS
    assemble_cues.py       # Step 5: assemble each cue segment
    concat_movement.py     # Step 6: concatenate into final MP3
  output/
    bumper.mp3             # shared across all movements
    mv1/
      mv1_commentary.mp3   # final deliverable
```

Score files are expected at:
```
C:\data\beethoven\serioso\score\mscz\IMSLP22095.mvt1.mscz
C:\data\beethoven\serioso\score\mxl\IMSLP22095.mvt1.mxl
```

---

## Running the pipeline

```powershell
python run_pipeline.py --cues cues_mv1.json --mscz IMSLP22095.mvt1.mscz --mxl IMSLP22095.mvt1.mxl --movement 1
```

### Flags

| Flag | Description |
|------|-------------|
| `--cues` | Cues JSON filename (looked up in `cues/`) |
| `--mscz` | MuseScore file (looked up in `score/mscz/`) |
| `--mxl` | MXL file for tempo map (looked up in `score/mxl/`) |
| `--movement` | Movement number (1–4) |
| `--skip-render` | Skip Step 1 if WAV already exists — saves time on reruns |

### Example: rerun without re-rendering the score

```powershell
python run_pipeline.py --cues cues_mv1.json --mscz IMSLP22095.mvt1.mscz --mxl IMSLP22095.mvt1.mxl --movement 1 --skip-render
```

---

## Cues JSON format

```json
{
  "movement": 1,
  "voice": "af_sarah",
  "speed": 0.92,
  "lang": "en-us",
  "silence_pre_clip_ms": 500,
  "silence_post_clip_ms": 1000,
  "silence_between_cues_ms": 1500,
  "clip_fade_in_ms": 300,
  "clip_fade_out_ms": 500,
  "bumper": { "vo": "...", "silence_after_ms": 1000 },
  "intro": { "vo": "...", "silence_after_ms": 1500 },
  "cues": [
    {
      "cue_id": "MV1_01",
      "clip_measures": [1, 2],
      "vo_pre": "...",
      "vo_post": "..."
    }
  ],
  "outro": { "silence_before_ms": 2000, "vo": "..." }
}
```

---

## Future movements

Once Movement 1 is confirmed, movements 2–4 run identically:

```powershell
python run_pipeline.py --cues cues_mv2.json --mscz IMSLP22095.mvt2.mscz --mxl IMSLP22095.mvt2.mxl --movement 2
python run_pipeline.py --cues cues_mv3.json --mscz IMSLP22095.mvt3.mscz --mxl IMSLP22095.mvt3.mxl --movement 3
python run_pipeline.py --cues cues_mv4.json --mscz IMSLP22095.mvt4.mscz --mxl IMSLP22095.mvt4.mxl --movement 4
```

`bumper.mp3` is generated once in Movement 1 and reused across all movements.

---

## Teaser pipeline

Produces a single cross-movement promotional MP3 (`teaser.mp3`) from cues that span all four movements.
Requires the per-movement WAVs to already exist — run all four movements first.

```powershell
python run_teaser.py
```

All arguments have defaults. Override as needed:

```powershell
python run_teaser.py `
  --cues cues_teaser.json `
  --mxl-dir C:\data\beethoven\serioso\score\mxl `
  --output output/teaser/teaser.mp3
```

### Flags

| Flag | Description |
|------|-------------|
| `--cues` | Teaser cues JSON filename (in `cues/`, default `cues_teaser.json`) |
| `--mxl-dir` | Directory containing MXL files (default: `score/mxl/`) |
| `--output` | Output MP3 path (default: `output/teaser/teaser.mp3`) |
| `--no-cache` | Re-render all clips and VO even if cached |

### How it differs from the per-movement pipeline

- Adds `source_movements` to the cues JSON — maps each movement number to its MXL file
- Each cue carries a `movement` field; clips are routed to the correct source WAV per cue
- Tempo maps are reused from `output/mv{N}/tempo_map.json` if present, otherwise built on demand
- Assembly is done in one pass with no intermediate assembled-cue files

### Directory structure added

```
listener-track/
  run_teaser.py
  pipeline/
    teaser_extract_clips.py   # multi-source clip extraction
  cues/
    cues_teaser.json
  output/
    teaser/
      clips/                  # TEASER_01_clip.mp3 … TEASER_08_clip.mp3
      vo/                     # voice-over segments
      silences/               # generated silence fills
      teaser.mp3              # final deliverable
```

### Teaser cues JSON — additional fields

```json
{
  "movement": 0,
  "source_movements": [
    { "mv": 1, "file": "IMSLP22095_mvt1.mxl", "total_measures": 151 },
    { "mv": 4, "file": "IMSLP22095_mvt4.mxl", "total_measures": 176 }
  ],
  "cues": [
    {
      "cue_id": "TEASER_01",
      "movement": 1,
      "clip_measures": [1, 2],
      "vo_pre": "...",
      "vo_post": "..."
    }
  ]
}
```

All other fields (`voice`, `speed`, `bumper`, `intro`, `outro`, silence/fade params) are identical to the per-movement format.
