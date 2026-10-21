"""Beat grid + downbeat candidates + precise transient attacks.

usage: python beats.py MEDIA [--from S] [--to S] [--near T ...] [--bpm 134]
Times are in MEDIA time (seconds).
"""
import argparse, subprocess, tempfile, os
import numpy as np, librosa

ap = argparse.ArgumentParser()
ap.add_argument("media"); ap.add_argument("--from", dest="a", type=float, default=0)
ap.add_argument("--to", dest="b", type=float, default=None)
ap.add_argument("--near", type=float, action="append", default=[])
ap.add_argument("--bpm", type=float, default=120)
o = ap.parse_args()

def load(a, dur, sr):
    tmp = tempfile.mktemp(suffix=".wav")
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(a)] + (["-t", str(dur)] if dur else []) + \
          ["-i", o.media, "-vn", "-ac", "1", "-ar", str(sr), tmp]
    subprocess.run(cmd, check=True); y, _ = librosa.load(tmp, sr=sr); os.remove(tmp); return y

sr = 22050
y = load(o.a, (o.b - o.a) if o.b else None, sr)
tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time", start_bpm=o.bpm)
beats = beats + o.a
tempo = float(np.atleast_1d(tempo)[0])
print(f"tempo ≈ {tempo:.2f} BPM  beat {60/tempo:.4f}s  bar(4/4) {240/tempo:.4f}s")

S = np.abs(librosa.stft(y, hop_length=256)); f = librosa.fft_frequencies(sr=sr)
low = S[f < 150].sum(0); tt = librosa.times_like(low, sr=sr, hop_length=256) + o.a
acc = np.zeros(4); vals = []
for i, x in enumerate(beats):
    k = np.argmin(abs(tt - x)); v = low[max(0, k-2):k+3].max(); vals.append(v); acc[i % 4] += v
print("kick energy by beat position (mod 4, from first tracked beat):", acc.round(0))
print("NB librosa beat times lag the real attack by ~20-30 ms; use --near for exact attacks.")
for T in o.near:
    print(f"\n-- around {T:.2f}: beats (time, kick, pos) --")
    for i, (x, v) in enumerate(zip(beats, vals)):
        if T - 4 < x < T + 4: print(f"  {x:8.3f}  {v:7.1f}  pos {i % 4}{'  <-- strong' if v > 2*np.median(vals) else ''}")
    cand = min(beats, key=lambda x: abs(x - T)) if len(beats) else T
    # attack precedes the librosa beat time: search [beat-0.15, beat+0.08] at 48 kHz
    seg = load(cand - 0.15, 0.23, 48000)
    e = np.convolve(seg**2, np.ones(48)/48, "same")
    k = int(np.argmax(np.diff(np.convolve(e, np.ones(240)/240, "same"))))  # steepest energy rise
    lo = max(0, k - 2880)                                                 # look back <= 60 ms
    base = np.median(e[max(0, lo - 2400):lo + 1]); top = e[k:k + 480].max()
    i = next((n for n in range(lo, k + 1) if e[n] > base + 0.1 * (top - base)), k)
    print(f"  nearest beat {cand:.3f}; transient attack ≈ {cand - 0.15 + i/48000:.3f}")
