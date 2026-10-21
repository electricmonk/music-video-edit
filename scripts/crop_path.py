"""Build a per-frame crop-x path (ffmpeg sendcmd file) from a JSON plan.

usage: python crop_path.py plan.json out.cmd
plan: {"src_w":3840, "crop_w":1216, "fps":25, "duration":60,
       "faces":"faces.txt", "sample_fps":5, "default_center":0.5,
       "segments":[{"start":0,"end":14.2,"mode":"track","smooth":0.7,"pick":"largest|leftmost|rightmost"},
                   {"start":22.6,"end":29.8,"mode":"pan","from":0.41,"to":0.54},
                   {"start":43.0,"end":49.6,"mode":"fixed","center":0.43}]}
Centers are fractions of source width. faces.txt is the output of the `faces` Vision tool on frames
sampled at sample_fps starting at t=0 (frame 1 = t 0).
Use with: -vf "sendcmd=f=out.cmd,crop=CROP_W:H:X0:0,scale=…"
"""
import json, sys
import numpy as np

p = json.load(open(sys.argv[1]))
W, CW, FPS, DUR = p["src_w"], p["crop_w"], p["fps"], p["duration"]
n = int(round(DUR * FPS)); ft = np.arange(n) / FPS
out = np.full(n, p.get("default_center", 0.5) * W - CW / 2)

faces = None
if "faces" in p:
    rows = [l.split() for l in open(p["faces"])]
    faces = []
    for r in rows:
        dets = [tuple(map(float, d.split(","))) for d in r[1:]]  # midX, width, midY, conf
        faces.append(dets)
    ts = np.arange(len(faces)) / p.get("sample_fps", 5)

for s in p["segments"]:
    m = (ft >= s["start"]) & (ft < s["end"])
    if not m.any(): continue
    if s["mode"] == "fixed":
        out[m] = s["center"] * W - CW / 2
    elif s["mode"] == "pan":
        u = (ft[m] - s["start"]) / (s["end"] - s["start"]); u = u * u * (3 - 2 * u)  # smoothstep
        out[m] = (s["from"] + (s["to"] - s["from"]) * u) * W - CW / 2
    elif s["mode"] == "track":
        pick = s.get("pick", "largest")
        xs, tx = [], []
        for t, d in zip(ts, faces):
            if not (s["start"] <= t < s["end"]) or not d: continue
            f = max(d, key=lambda q: q[1]) if pick == "largest" else min(d, key=lambda q: q[0]) if pick == "leftmost" else max(d, key=lambda q: q[0])
            tx.append(t); xs.append(f[0])
        if not tx: print("no faces in", s); continue
        x = np.interp(ft[m], tx, xs) * W - CW / 2
        sig = s.get("smooth", 0.7) * FPS; k = np.arange(-3 * int(sig), 3 * int(sig) + 1)
        g = np.exp(-k**2 / (2 * sig**2)); g /= g.sum()
        out[m] = np.convolve(np.pad(x, len(k) // 2, mode="edge"), g, "valid")
out = np.clip(out, 0, W - CW)
with open(sys.argv[2], "w") as fh:
    for t, x in zip(ft, out): fh.write("%.3f crop x %d;\n" % (t, round(x)))
print("x per second:", " ".join("%d:%d" % (t, x) for t, x in zip(ft[::FPS], out[::FPS])))
print("clamped at edge:", f"{(np.isclose(out, 0) | np.isclose(out, W - CW)).mean()*100:.0f}% of frames")
