"""Find exact caption spans for sung lyric lines.

usage: python align_lyrics.py MEDIA --lyrics lyrics.txt --out WORKDIR [--ss START] [--t DUR] [--lang he] [--lead 0.1]
lyrics.txt: one caption line per row, in sung order (repeats written out).
Writes WORKDIR/captions.json ([{start,end,text}], times relative to --ss), WORKDIR/words.json, WORKDIR/onsets.png.
"""
import argparse, json, os, re, subprocess, sys, unicodedata
import numpy as np, librosa

ap = argparse.ArgumentParser()
ap.add_argument("media"); ap.add_argument("--lyrics", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--ss", type=float, default=0); ap.add_argument("--t", type=float, default=None)
ap.add_argument("--lang", default="he"); ap.add_argument("--lead", type=float, default=0.1)
ap.add_argument("--model", default="turbo")
o = ap.parse_args(); os.makedirs(o.out, exist_ok=True)
lines = [l.strip() for l in open(o.lyrics, encoding="utf-8") if l.strip()]

# 1. extract + separate vocals
wav = f"{o.out}/mix.wav"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(o.ss)] + (["-t", str(o.t)] if o.t else []) +
               ["-i", o.media, "-vn", "-ar", "44100", wav], check=True)
voc = f"{o.out}/htdemucs/mix/vocals.wav"
if not os.path.exists(voc):
    subprocess.run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "-o", o.out, wav], check=True)

# 2. whisper word timestamps
wj = f"{o.out}/words.json"
if not os.path.exists(wj):
    import whisper
    r = whisper.load_model(o.model).transcribe(voc, language=o.lang, word_timestamps=True,
                                              initial_prompt=" ".join(dict.fromkeys(lines)))
    json.dump([{"w": w["word"].strip(), "s": w["start"], "e": w["end"]} for s in r["segments"] for w in s["words"]],
              open(wj, "w"), ensure_ascii=False, indent=1)
words = json.load(open(wj))

def norm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))
    return re.sub(r"[^\w]", "", s)

# 3. match lines to words: character-level alignment (robust to Whisper mishearings)
import difflib
wchars, wmap = [], []
for k, w in enumerate(words):
    for ch in norm(w["w"]): wchars.append(ch); wmap.append(k)
lchars, lstart, lend = [], [], []
for ln in lines:
    lstart.append(len(lchars)); lchars += list(norm(ln.replace(" ", ""))); lend.append(len(lchars) - 1)
sm = difflib.SequenceMatcher(None, lchars, wchars, autojunk=False)
l2w = {}
for a, b, size in sm.get_matching_blocks():
    for d in range(size): l2w[a + d] = b + d
def map_char(i, direction):
    for d in range(0, 12):
        j = i + d * direction
        if j in l2w: return wmap[l2w[j]]
    return None
matched = []
for ln, a, b in zip(lines, lstart, lend):
    j, e = map_char(a, +1), map_char(b, -1)
    if j is None or e is None or e < j: print("!! could not match:", ln); matched.append(None)
    else: matched.append((j, e))

# 4. refine onsets on the vocal envelope
y, sr = librosa.load(voc, sr=22050, mono=True)
hop = 110
db = 20 * np.log10(librosa.feature.rms(y=y, frame_length=1024, hop_length=hop)[0] + 1e-6)
t = np.arange(len(db)) * hop / sr; pk = np.percentile(db, 95)
dur = len(y) / sr

def onset_before(anchor, floor):
    """start of the voiced region that contains `anchor` (end of the line's first word):
    walk back to the last >=80 ms quiet run (M-20 dB, M = local max), then forward to M-12 dB.
    Slow fade-ins can land a few hundred ms late; breathy starts can land early. Always check onsets.png."""
    a = max(floor, anchor - 2.5)
    idx = np.where((t >= a) & (t < anchor))[0]
    if not len(idx): return anchor
    M = db[np.where((t >= a) & (t < anchor + 0.5))[0]].max()
    quiet = db[idx] < M - 20
    run, last_quiet_end = 0, None
    for n, q in enumerate(quiet):
        run = run + 1 if q else 0
        if run * hop / sr >= 0.08: last_quiet_end = n
    if last_quiet_end is not None:
        for n in range(last_quiet_end, len(idx)):
            if db[idx[n]] > M - 12: return t[idx[n]]
    d = np.diff(db[idx]); return t[idx[np.argmax(d)]] if len(d) else anchor

caps, prev_end = [], 0.0
for ln, mt in zip(lines, matched):
    if mt is None: continue
    j, e = mt
    anchor = words[j]["e"] if j + 1 < len(words) else words[j]["s"]
    on = onset_before(anchor, prev_end)
    last = words[e]["e"]
    caps.append({"text": ln, "onset": on, "last_word_end": last}); prev_end = last
for i, c in enumerate(caps):
    nxt = caps[i + 1]["onset"] if i + 1 < len(caps) else dur
    idx = np.where((t > c["last_word_end"] - 0.3) & (t < nxt - 0.1))[0]
    loud = idx[db[idx] > pk - 15]
    end = min((t[loud[-1]] + 0.3) if len(loud) else c["last_word_end"] + 0.3, nxt - 0.15, dur - 0.15)
    c["start"] = round(max(0, c["onset"] - o.lead), 3); c["end"] = round(end, 3)
json.dump([{"start": c["start"], "end": c["end"], "text": c["text"]} for c in caps],
          open(f"{o.out}/captions.json", "w"), ensure_ascii=False, indent=1)
for c in caps: print(f"{c['start']:7.2f} – {c['end']:7.2f}  (onset {c['onset']:.2f})  {c['text']}")

# 5. diagnostic plot
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
n = len(caps); cols = 2; rows = (n + 1) // 2
fig, axs = plt.subplots(rows, cols, figsize=(16, 2.8 * rows), squeeze=False)
for k, c in enumerate(caps):
    ax = axs[k % rows][k // rows]; a, b = max(0, c["onset"] - 1.5), min(dur, c["onset"] + 1.5)
    seg = y[int(a * sr):int(b * sr)]
    Sx = librosa.amplitude_to_db(np.abs(librosa.stft(seg, n_fft=1024, hop_length=64)), ref=np.max)
    ax.imshow(Sx[:200], origin="lower", aspect="auto", extent=[a, b, 0, 200 * sr / 1024], vmin=-60, cmap="magma")
    m = (t >= a) & (t <= b); ax2 = ax.twinx(); ax2.plot(t[m], db[m], c="cyan", lw=1)
    ax.axvline(c["onset"], c="lime", ls="--"); ax.axvline(c["start"], c="w", ls=":")
    ax.set_title(f"line {k+1}: onset {c['onset']:.2f}")
plt.tight_layout(); plt.savefig(f"{o.out}/onsets.png", dpi=70)
print("plot:", f"{o.out}/onsets.png")
