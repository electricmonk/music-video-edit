"""Overlay caption PNGs (rendered with the `caption` CoreText tool) onto a video.

usage: python burn_captions.py captions.json OUT.mp4 --in "<ffmpeg input args>" [--vf PREFILTER] [--af AUDIOFILTER]
         --font FILE [--t DUR] [--wght 500] [--size 80] [--y 1420] [--stroke 7] [--fade 0.15]
captions.json: [{"start":1.03,"end":6.17,"text":"..."}, ...]  (times relative to output start)
--in example: '-ss 120 -t 60 -i "/path/video.mp4"'  (first input must be the video+audio)
--vf example: 'sendcmd=f=crop.cmd,crop=1216:2160:1312:0,scale=1080:1920:flags=lanczos'
Output frame must be 1080x1920 (caption canvas size); scale in --vf if needed.
"""
import argparse, json, os, shlex, subprocess, tempfile

MV = os.path.expanduser("~/.cache/music-video-edit")
ap = argparse.ArgumentParser()
ap.add_argument("captions"); ap.add_argument("out")
ap.add_argument("--in", dest="inp", required=True); ap.add_argument("--vf", default="null")
ap.add_argument("--af", default=None); ap.add_argument("--t", default=None)
ap.add_argument("--font", required=True, help="font file, or - for the system font (use the project's approved style)")
ap.add_argument("--wght", default="500"); ap.add_argument("--size", default="80")
ap.add_argument("--y", default="1420"); ap.add_argument("--stroke", default="7")
ap.add_argument("--fade", type=float, default=0.15)
o = ap.parse_args()

# -ss must sit on a frame boundary: otherwise every sendcmd crop change lands one frame after the camera cut
# (a 1-frame flash of the new shot framed for the old one)
a = shlex.split(o.inp)
if "-ss" in a and "-i" in a:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "csv=p=0", a[a.index("-i") + 1]], capture_output=True, text=True).stdout.strip()
    if r:
        n, d = map(int, r.split("/")); fps = n / d; f = float(a[a.index("-ss") + 1]) * fps
        if abs(f - round(f)) > 0.01:
            raise SystemExit(f"-ss {a[a.index('-ss') + 1]} is not on a frame boundary at {fps:g} fps; use {round(f) / fps:.3f} or {(round(f) + (1 if f > round(f) else -1)) / fps:.3f}")
caps = json.load(open(o.captions)); tmp = tempfile.mkdtemp()
inputs, fc, prev = [], [f"[0:v]{o.vf}[v]"], "[v]"
for i, c in enumerate(caps):
    png = f"{tmp}/c{i}.png"; dur = c["end"] - c["start"]
    subprocess.run([f"{MV}/bin/caption", c["text"], png, o.size, o.y, o.font, o.wght, o.stroke], check=True)
    inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", png]
    fc.append(f"[{i+1}]format=rgba,fade=in:st=0:d={o.fade}:alpha=1,fade=out:st={dur-o.fade:.3f}:d={o.fade}:alpha=1,"
              f"setpts=PTS+{c['start']:.3f}/TB[c{i}]")
    nxt = f"[o{i}]" if i < len(caps) - 1 else "[vout]"
    fc.append(f"{prev}[c{i}]overlay=eof_action=pass{nxt}"); prev = nxt
if not caps: fc[-1] = fc[-1].replace("[v]", "[vout]")
cmd = ["ffmpeg", "-v", "error", "-y"] + shlex.split(o.inp) + inputs + ["-filter_complex", ";".join(fc),
       "-map", "[vout]", "-map", "0:a?"] + (["-af", o.af] if o.af else []) + \
      ["-c:v", "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k"] + \
      (["-t", o.t] if o.t else []) + ["-movflags", "+faststart", o.out]
subprocess.run(cmd, check=True); print("wrote", o.out)
