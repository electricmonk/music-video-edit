"""Caption style comparison sheet: one labeled strip per font/weight/stroke variant over a real frame.

usage: python font_sheet.py "<caption text>" OUT.png (--frame IMG | --video V --at SECONDS [--vf PREFILTER])
         [--variant FONT[:WGHT[:STROKE[:SIZE]]] ...] [--fonts-glob '*'] [--y 1420] [--size 80] [--wght 500] [--stroke 7]
FONT is a path or a file name inside ~/.cache/music-video-edit/fonts (prefix match ok, e.g. "Heebo"), or "-" for the system font.
Without --variant, every font in the fonts dir is shown with the default weight/stroke/size.
The frame is scaled/cropped to 1080x1920 (the caption canvas). Prints a numbered legend; the same numbers are drawn on the sheet.
Examples:
  font_sheet.py "שורה לדוגמה" fonts.png --video reel.mp4 --at 2
  font_sheet.py "שורה" weights.png --frame f.png --variant Assistant:300 --variant Assistant:500 --variant Assistant:700
  font_sheet.py "שורה" strokes.png --frame f.png --variant Heebo:500:0 --variant Heebo:500:5 --variant Heebo:500:10
"""
import argparse, glob, os, subprocess, tempfile

MV = os.path.expanduser("~/.cache/music-video-edit"); CAP = f"{MV}/bin/caption"
ap = argparse.ArgumentParser()
ap.add_argument("text"); ap.add_argument("out")
ap.add_argument("--frame"); ap.add_argument("--video"); ap.add_argument("--at", type=float, default=0)
ap.add_argument("--vf", default=None, help="prefilter applied to the video frame before fitting to 1080x1920 (e.g. your crop)")
ap.add_argument("--variant", action="append", default=[])
ap.add_argument("--fonts-glob", default="*")
ap.add_argument("--y", type=int, default=1420); ap.add_argument("--size", default="80")
ap.add_argument("--wght", default="500"); ap.add_argument("--stroke", default="7")
ap.add_argument("--strip", type=int, default=260, help="strip height in px")
o = ap.parse_args()
tmp = tempfile.mkdtemp()

def run(*a): subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)

# 1. background frame at 1080x1920
fit = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
bg = f"{tmp}/bg.png"
if o.frame: run("-i", o.frame, "-vf", fit, "-frames:v", "1", bg)
elif o.video: run("-ss", str(o.at), "-i", o.video, "-vf", (o.vf + "," if o.vf else "") + fit, "-frames:v", "1", bg)
else: ap.error("--frame or --video required")

def resolve(f):
    if f == "-" or os.path.exists(f): return f
    hits = sorted(glob.glob(f"{MV}/fonts/{f}*"))
    if not hits: raise SystemExit(f"font not found: {f}")
    return hits[0]

variants = []
for v in o.variant:
    p = v.split(":"); f = resolve(p[0])
    variants.append((f, p[1] if len(p) > 1 and p[1] else o.wght, p[2] if len(p) > 2 and p[2] else o.stroke,
                     p[3] if len(p) > 3 and p[3] else o.size))
if not variants:
    variants = [(f, o.wght, o.stroke, o.size) for f in sorted(glob.glob(f"{MV}/fonts/{o.fonts_glob}")) if f.endswith((".ttf", ".otf"))]

# 2. one strip per variant: caption + small numbered label at the top
top = max(0, o.y - o.strip // 2); strips = []
for i, (f, w, s, z) in enumerate(variants, 1):
    name = "system" if f == "-" else os.path.basename(f).rsplit(".", 1)[0]
    cap, lab, st = f"{tmp}/c{i}.png", f"{tmp}/l{i}.png", f"{tmp}/s{i:02d}.png"
    subprocess.run([CAP, o.text, cap, z, str(o.y), f, w, s], check=True)
    subprocess.run([CAP, f"{i}  {name}  w{w} s{s}", lab, "26", str(top + 22), "-", "500", "6", "ltr"], check=True)
    run("-i", bg, "-i", cap, "-i", lab, "-filter_complex",
        f"[0][1]overlay[a];[a][2]overlay,crop=1080:{o.strip}:0:{top},drawbox=y=ih-2:h=2:color=white@0.6:t=fill", st)
    strips.append(st); print(f"{i}: {name}  weight {w}  stroke {s}  size {z}")
run("-i", f"{tmp}/s%02d.png", "-vf", f"tile=1x{len(strips)}", "-frames:v", "1", o.out)
print("sheet:", o.out)
