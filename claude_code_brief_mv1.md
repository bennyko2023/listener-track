# Claude Code Brief — Op. 95 Listener Track Pipeline
# Beethoven String Quartet in F minor, Op. 95 ("Serioso")
# Product: Fugual.com guided listening commentary track

---

## OBJECTIVE

Build a Python pipeline that takes:
- A cues JSON file (one per movement)
- A MuseScore .mscz file (one per movement)

And produces:
- One fully assembled MP3 commentary file per movement

Format per movement file:
  bumper → intro → [vo_pre → clip → vo_post] × N cues → outro

---

## ENVIRONMENT

- OS: Windows 11
- Python: 3.14
- MuseScore 4.6.5 CLI: "C:\Program Files\MuseScore 4\bin\MuseScore4.exe"
- FFmpeg 8.1: C:\ffmpeg\bin\ffmpeg.exe (on PATH)
- Kokoro TTS: kokoro-onnx installed via pip
- Kokoro model files location: C:\data\beethoven\serioso\listener track\
    - kokoro-v1.0.onnx
    - voices-v1.0.bin
- Working directory: C:\data\beethoven\serioso\listener track\

---

## INPUT FILES

### Cues JSON
C:\data\beethoven\serioso\listener track\cues_mv1.json

Structure:
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
    },
    ...
  ],
  "outro": { "silence_before_ms": 2000, "vo": "..." }
}

### Score file
C:\data\beethoven\serioso\IMSLP22095.mvt1.mscz

### MXL file (for tempo map extraction)
C:\data\beethoven\serioso\IMSLP22095.mvt1.mxl

---

## OUTPUT STRUCTURE

C:\data\beethoven\serioso\listener track\
  output\
    mv1\
      wav\
        mv1_full.wav              # full movement render from MuseScore
      clips\
        MV1_01_clip.mp3
        MV1_02_clip.mp3
        ...
      vo\
        bumper.mp3                # reused across all movements
        mv1_intro.mp3
        MV1_01_vo_pre.mp3
        MV1_01_vo_post.mp3
        ...
        mv1_outro.mp3
      assembled\
        MV1_01.mp3
        MV1_02.mp3
        ...
      mv1_commentary.mp3          # final deliverable

---

## PIPELINE SCRIPTS

Build the following scripts in the working directory:

---

### 1. render_score.py
Purpose: Export full movement WAV from MuseScore CLI.

Logic:
- Call MuseScore4.exe -o output/mv1/wav/mv1_full.wav mscz_path
- Detect and log output file size
- Abort if file is missing or under 100KB (failed render)

---

### 2. build_tempo_map.py
Purpose: Extract measure-to-timestamp lookup from MXL using music21.

Logic:
- Install music21 if not present: pip install music21
- Parse the MXL
- Walk all measures, accumulate time in seconds using tempo markings
  and time signature beat durations
- Detect any leading silence in mv1_full.wav (first non-silent frame)
  and add as offset to all timestamps
- Output: output/mv1/tempo_map.json
  Format: { "1": 0.00, "2": 1.44, "3": 2.88, ... }

Notes:
- If multiple tempo markings exist, apply each from its measure onward
- If no tempo marking found, default to quarter = 120
- Leading silence detection: scan WAV with librosa or pydub,
  find first frame above -50dB threshold

---

### 3. extract_clips.py
Purpose: Cut measure-range clips from full WAV using FFmpeg.

Logic:
- Load tempo_map.json
- For each cue in cues JSON:
  - measure_start = clip_measures[0]
  - measure_end = clip_measures[1]
  - t_start = tempo_map[measure_start]
  - t_end = tempo_map[measure_end + 1]  # start of next measure = end of clip
  - duration = t_end - t_start
  - Run FFmpeg:
    ffmpeg -i mv1_full.wav
           -ss t_start
           -t duration
           -af "afade=t=in:st=0:d=fade_in, afade=t=out:st=(duration-fade_out):d=fade_out"
           output/mv1/clips/MV1_XX_clip.mp3
- fade_in and fade_out durations from JSON (clip_fade_in_ms, clip_fade_out_ms)

---

### 4. generate_vo.py
Purpose: Generate all VO lines via Kokoro TTS.

Logic:
- Load Kokoro model from working directory
- For each text segment (bumper, intro, each cue vo_pre and vo_post, outro):
  - Generate WAV via kokoro.create(text, voice=voice, speed=speed, lang=lang)
  - Save WAV to output/mv1/vo/
  - Convert WAV to MP3 via FFmpeg
- bumper.mp3 saved at output level (not mv1 subfolder) — reused across movements
- Log character count per segment

---

### 5. assemble_cues.py
Purpose: Assemble each cue as: vo_pre + silence + clip + silence + vo_post.

Logic:
- For each cue:
  - Build FFmpeg concat list:
    vo_pre.mp3
    silence_pre_clip (generated silence file)
    clip.mp3
    silence_post_clip
    vo_post.mp3
    silence_between_cues
  - Use FFmpeg concat demuxer to join
  - Output: output/mv1/assembled/MV1_XX.mp3

Silence generation:
  ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t 0.5 silence_500ms.mp3
  Generate once for each required duration, reuse.

---

### 6. concat_movement.py
Purpose: Concatenate all segments into final movement file.

Logic:
- Build concat list in order:
  bumper.mp3
  silence (1000ms)
  mv1_intro.mp3
  silence (1500ms)
  MV1_01.mp3
  MV1_02.mp3
  ... all assembled cues in order ...
  silence (2000ms)
  mv1_outro.mp3
- FFmpeg concat → output/mv1/mv1_commentary.mp3
- Log total duration

---

### 7. run_pipeline.py
Purpose: Master script — runs all steps in sequence for one movement.

Usage:
  python run_pipeline.py --cues cues_mv1.json --mscz IMSLP22095.mvt1.mscz --mxl IMSLP22095.mvt1.mxl --movement 1

Logic:
- Step 1: render_score.py
- Step 2: build_tempo_map.py
- Step 3: extract_clips.py
- Step 4: generate_vo.py
- Step 5: assemble_cues.py
- Step 6: concat_movement.py
- Report: total duration, file size, any errors
- On any step failure: log error, abort, report which step failed

---

## DEPENDENCIES

Install before running:
  pip install music21 kokoro-onnx soundfile numpy pydub librosa

FFmpeg must be on PATH (confirmed).

---

## CRITICAL NOTES

1. WAV not MP3 from MuseScore — MuseScore CLI MP3 export is malformed on
   this system. Always export WAV, convert to MP3 via FFmpeg.

2. Leading silence offset — MuseScore WAV exports may include silence
   before beat 1. Detect and subtract this offset in build_tempo_map.py
   or all clips will be misaligned.

3. Measure end boundary — clip end timestamp = start of (measure_end + 1),
   not end of measure_end. Use tempo_map[str(measure_end + 1)].

4. Bumper reuse — bumper.mp3 is rendered once and reused across all four
   movements. Do not re-render per movement.

5. Path handling — all paths use Windows backslash or pathlib.Path for
   cross-platform safety.

6. Kokoro model path — model files are in the working directory:
   C:\data\beethoven\serioso\listener track\
   Pass full paths explicitly to Kokoro constructor.

---

## FIRST RUN TARGET

Produce output/mv1/mv1_commentary.mp3 from:
- cues_mv1.json
- IMSLP22095.mvt1.mscz
- IMSLP22095.mvt1.mxl

Report total duration and flag any cue where clip length is under 5 seconds
(likely a tempo map error).

---

## FUTURE MOVEMENTS

Once MV1 pipeline is confirmed, movements 2–4 run identically:
- cues_mv2.json + IMSLP22095.mvt2.mscz + IMSLP22095.mvt2.mxl → mv2_commentary.mp3
- cues_mv3.json + IMSLP22095.mvt3.mscz + IMSLP22095.mvt3.mxl → mv3_commentary.mp3
- cues_mv4.json + IMSLP22095.mvt4.mscz + IMSLP22095.mvt4.mxl → mv4_commentary.mp3

No pipeline changes required between movements.
