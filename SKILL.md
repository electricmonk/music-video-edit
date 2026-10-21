---
name: music-video-edit
description: Cut and export music video clips with ffmpeg on macOS. Covers audio snippets over a still image, swapping a video's audio, musically clean cuts on downbeats, Instagram 9:16 / 3:4 crops with face-follow and pans, and Hebrew/RTL lyric captions synced to the vocal (Demucs + Whisper). Use for reels, teasers, lyric videos and timecode-based cuts of songs.
---

# Music video editing & lyric sync

Recipes, tools and hard-won lessons for turning songs and performance videos into reels, teasers and lyric videos.
Everything runs locally: ffmpeg + a Python venv (librosa, demucs, whisper) + small Swift tools (Vision faces, CoreText captions).

## 0. Setup (once per machine, idempotent)

```bash
~/.claude/skills/music-video-edit/scripts/setup.sh
```
Creates `~/.cache/music-video-edit/{venv,fonts,bin}`. Variables used below:
```bash
SK=~/.claude/skills/music-video-edit/scripts
MV=~/.cache/music-video-edit;  PY=$MV/venv/bin/python
```
Gotchas the setup handles or that you may hit:
- **Homebrew ffmpeg has no `drawtext`/`subtitles`/libass.** Never plan on burning text with ffmpeg; render caption PNGs with `caption` (CoreText) and `overlay` them.
- **Swift needs the Xcode license accepted** (`sudo xcodebuild -license`); ask the user to do it if `swift` complains — it's the user's call, not yours.
- OpenCV 5 dropped Haar cascades — use macOS Vision (`faces` tool) for face detection instead.
- pip installs can be slow; run setup in the background if needed. The Whisper `turbo` model is a 1.5 GB download on first use.

## 1. Timecodes — confirm the format first

Users often paste DAW timecode. `0:22:18.18` in a 4‑minute song is **not** h:mm:ss — it's Logic-style `m:ss:ff.sf` (frames + 1/80 subframes). Check the media duration with ffprobe, state your interpretation, assume 25 fps if unknown (PAL regions; ask otherwise), and offer to redo:
`seconds = m*60 + s + (ff + sf/80)/fps`.
When cutting a reel from a video, plain `m:ss` usually means video time.

## 2. Basic recipes

Audio snippet over a still image (keep image dimensions):
```bash
ffmpeg -loop 1 -framerate 25 -i cover.jpg -ss START -t DUR -i song.wav \
  -map 0:v -map 1:a -c:v libx264 -tune stillimage -pix_fmt yuv420p \
  -c:a aac -b:a 320k -t DUR -movflags +faststart out.mp4
```
**Use `-t DUR` on the output, not `-shortest`** — with a looped image `-shortest` overshoots by seconds.

Replace a video's audio with a snippet (and shorten): `-ss VSTART -i video.MOV -ss ASTART -t DUR -i song.wav -map 0:v -map 1:a … -t DUR`. Re-encode HEVC .MOV to H.264 (`-crf 16 -preset slow`) for compatibility.

Always verify with `ffprobe -show_entries format=duration:stream=codec_type,width,height,duration`, and *look* at results:
```bash
$SK/stills.sh out.mp4 check.jpg [--width 270] [--cols N] [--vf "<crop>"] 1 16 26 46   # numbered grid of frames at those times
```
Then Read the image. Use it for contact sheets (one time per shot), framing previews (pass the crop as `--vf`) and post-render checks.

## 3. Musically clean cuts (downbeats)

```bash
$PY $SK/beats.py media.mp4 --from 170 --to 250 --near 187 --near 245 [--bpm 120]
```
Prints tempo, the beat grid with low-band (kick) energy per beat, accent per bar position, and for each `--near` the refined transient attack time (5 ms resolution).
How to read it:
- A section "one" is typically a huge kick right after a quiet bar/beat. Confirm by counting: section lengths should be whole bars (e.g. exactly 32 bars apart). Bar = 4 × 60/BPM.
- Start the cut ~30–60 ms **before** the attack, snapped to a video frame boundary (multiple of 1/fps) so the transient isn't clipped; 10 ms audio fade-in.
- "End on the one of bar N" = **include** that downbeat: cut one beat after the attack with a ~0.25 s fade-out. Ending *just before* it is a different thing (seamless loop) — ask if unclear.
- Use `-ss` before `-i` (fast + frame-accurate when re-encoding).

## 4. Vertical crops & the face-follow trick

**Formats:** Reels are **9:16 → 1080×1920** (3:4 → 1080×1440 is a feed post, so confirm which). From 3840×2160, a 9:16 crop is 1216×2160 (centered x=1312) and a 3:4 crop is 1620×2160 (x=1110). Always make a plain centered version first; the face-follow cut is an alternate.

### Face-follow recipe (ffmpeg has no tracking; we drive `crop` per frame)
1. **Shots:** `$SK/shots.sh video.mp4 START DUR 5` lists the cut times. Use threshold 5: 12 misses soft cuts.
2. **Faces:** sample frames at 5 fps and run macOS Vision:
   ```bash
   mkdir frames && ffmpeg -ss START -t DUR -i video.mp4 -vf fps=5,scale=960:540 -q:v 3 frames/f%04d.jpg
   $MV/bin/faces frames > faces.txt   # "f0001.jpg midX,width,midY,conf ..." (normalized; frame n = t (n-1)/5)
   ```
   Face width tells shot type: about 0.2 means a close-up, about 0.03 means a wide shot. Several detections mean a group shot. Wide-shot faces may need full-res frames to be detected.
3. **Look before deciding:** `$SK/stills.sh video.mp4 shots.jpg <one time per shot>` and Read it. Identify who is who and ask which person is the subject when unclear; never assume (the person behind the camera or keyboard may be the user).
4. **Plan the framing per shot** (centers are fractions of source width; unlisted time is centered):
   ```json
   {"src_w":3840,"crop_w":1216,"fps":25,"duration":60,"faces":"faces.txt","sample_fps":5,
    "segments":[
     {"start":0,"end":14,"mode":"track","smooth":0.7,"pick":"largest"},
     {"start":22,"end":30,"mode":"pan","from":0.41,"to":0.54},
     {"start":30,"end":43,"mode":"track"},
     {"start":43,"end":50,"mode":"fixed","center":0.43}]}
   ```
   - `track`: interpolates the face's midX and applies Gaussian smoothing (0.7 s, so it glides and doesn't jitter). It's applied per segment, so it never smooths across a cut.
   - `pan`: a smoothstep ease from one center to another, for two people who don't both fit.
   - `fixed`: a static reframe, e.g. favouring the singer in a two-shot.
5. **Build and render:**
   ```bash
   $PY $SK/crop_path.py plan.json crop.cmd   # prints x per second and % of frames clamped at the frame edge
   ffmpeg -ss START -t DUR -i video.mp4 -vf "sendcmd=f=crop.cmd,crop=1216:2160:1312:0,scale=1080:1920:flags=lanczos" ...
   ```
   `crop`'s `x` accepts runtime commands; sendcmd times are output-relative because `-ss` comes before `-i`.
6. **Verify:** `$SK/stills.sh` on the render at times inside every tracked/reframed shot, and Read it.

Framing rules that worked:
- **Follow a face only when it is alone in a close-up.** Every other shot stays centered or gets a fixed or pan reframe.
- At 9:16, wide and two-shots that looked fine at 3:4 start cutting people off, so recheck them whenever the aspect ratio changes.
- When a subject drifts beyond what the crop can reach, the crop clamps at the edge. Tell the user (zooming in would be the only fix).
- When two people don't fit, offer three options: a slow pan from one to the other (usually the favourite), splitting the difference, or favouring one.

## 5. Captions (Hebrew / RTL)

Render: `$MV/bin/caption "<text>" out.png <size> <centerY> <fontfile|-> <wght> <stroke%> [rtl|ltr]` → 1080×1920 transparent PNG, centered paragraph (RTL by default; pass `ltr` for Latin-script lyrics), black stroke drawn under white fill, soft shadow.
**Good default style:** white Frank Ruhl Libre (`$MV/fonts/FrankRuhlLibre[wght].ttf`), weight 500, size 80, centerY 1420 (above the IG bottom UI), stroke 7 (thin; ~20 looks heavy), soft shadow, no trailing full stops. The macOS SF Hebrew system font looks generic. Niqqud renders fine with the bundled fonts. Always show a test frame before burning the whole clip.
**Choosing a style: show, don't ask.** Instead of describing fonts, render a labelled comparison sheet over a real frame of the clip and let the user pick a number:
```bash
$PY $SK/font_sheet.py "<a real lyric line>" fonts.png --video clip.mp4 --at 2          # every bundled font
$PY $SK/font_sheet.py "<line>" weights.png --video clip.mp4 --at 2 --variant Frank:300 --variant Frank:500 --variant Frank:700
$PY $SK/font_sheet.py "<line>" strokes.png --frame still.png --variant Heebo:500:0 --variant Heebo:500:5 --variant Heebo:500:10
```
Variants are `FONT[:WGHT[:STROKE[:SIZE]]]` (font = path, a prefix of a bundled font file, or `-` for the system font). Each strip is numbered and the legend is printed. Iterate one dimension at a time (font → weight → outline → size/position), then render one full test frame before burning the clip. Send sheets with SendUserFile.
Bundled free fonts (Hebrew + Latin): Heebo, Assistant, Rubik, Frank Ruhl Libre, Noto Sans/Serif Hebrew, David Libre, Varela Round, Secular One, Suez One, Karantina. For other scripts, drop more fonts into `$MV/fonts`. If the artwork uses a specific font, ask for the file.
Burn: `$PY $SK/burn_captions.py captions.json out.mp4 --in '-ss S -t D -i "video.mp4"' --vf "<crop/scale prefilter>" --af "<audio fades>" --t D` (see the docstring); each caption fades in/out 0.15 s. Re-render from the source each time (no generational loss).

## 6. Lyric sync — find the real spot

User-supplied times are usually the *stressed* word, often 0.2–0.9 s late; captions should appear at the phrase onset.
```bash
$PY $SK/align_lyrics.py media.mp4 --ss START --t DUR --lyrics lyrics.txt --out work/ [--lang he]
```
`lyrics.txt`: one caption line per row, in sung order (write repeats out). The script:
1. Separates vocals with **Demucs** (`htdemucs --two-stems=vocals`, ~5 s per minute on Apple silicon).
2. Runs **Whisper turbo** with word timestamps, lyrics as `initial_prompt`.
3. Matches lines to words by **character-level alignment** (difflib, ignoring niqqud and punctuation). Whisper mishears sung lyrics (wrong or split words), differs from run to run, and hallucinates filler such as "תודה רבה" on trailing silence, so exact word matching fails. `words.json` and the Demucs output are cached in the work dir; delete them to redo.
4. Refines each onset: Whisper's *first-word start is padded* (unreliable), but the boundary first-word-end/second-word-start is reliable. So it walks back from there to the last ≥80 ms silence on the isolated vocal, then forward to the voice rise. In testing it landed within about 0.15 s on 9 of 10 lines; a slow fade-in landed 0.6 s late, so nudge outliers by hand from the plot.
5. Ends each caption while the vocal is still sustained (held notes can last ~7 s), capped before the next line.
6. Writes `captions.json` (start = onset − 0.1 s) and `onsets.png` (spectrogram + envelope per line) — **Read the PNG and sanity-check**, especially breathy starts (Hebrew ח/ה are noise, not harmonics) and long melismas.
Report a table of old vs new times, and call out lines that moved a lot or contradict what the user said was already right.
Musical repeats: a second chorus usually sits exactly N bars later (e.g. 16 bars = 28.65 s at 134 BPM; bar = 240/BPM s) — use that as a cross-check.

## 7. Delivery

- Output next to the source file with descriptive names (`… - Reel 9x16 (face follow, captions).mp4`); keep earlier variants unless told otherwise.
- Encode: H.264 `-crf 17 -preset slow -pix_fmt yuv420p`, AAC 320k, `-movflags +faststart`.
- General principle: whenever there's a visual choice (font, framing, crop position), render the options side by side and let the user pick, instead of describing them in words.
- Send stills / test frames with SendUserFile for visual approval before long renders; say what you verified (stills) vs not (motion/sound).
