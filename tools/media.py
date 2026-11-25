"""Build the site's media from the staged source footage.

Usage:
  python3 tools/media.py check   -> contact sheet of each reel segment (first/mid/last frame)
  python3 tools/media.py build   -> reel, card previews, stills, case-study clips into static/media
Sources live in /home/claude/assets/src (symlinks to the staged originals).
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw

SRC = "/home/claude/assets/src"
OUT = "/home/claude/ilvera-site/static/media"
TMP = "/home/claude/assets/tmp"
os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)

# Reel segments, in playback order. mode h = 16:9 source, v = 9:16 source shown as a phone tile.
SEGMENTS = [
    dict(id="tsp-infinity", src="tsp_infinity_reveal.mp4", start=1.8, dur=3.4, mode="h"),
    dict(id="tsp-mandelbrot", src="tsp_mandelbrot.mp4", start=2.0, dur=3.4, mode="h"),
    dict(id="sienna",       src="sienna_morphy_169.mp4", start=6.0, dur=3.4, mode="h"),
    dict(id="wvhh",         src="wvhh_jackie_raw2.mp4", start=0.6, dur=3.4, mode="v"),
    dict(id="lights-on",    src="lights_ep1.mp4", start=41.0, dur=3.4, mode="h"),
]

def run(cmd):
    subprocess.run(cmd, check=True)

def ff(*args):
    run(["ffmpeg", "-v", "error", "-y", *args])

def phone_mask(w, h, r, path):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    m.save(path)

def segment(seg, out, w=1280, h=720):
    s = os.path.join(SRC, seg["src"])
    if seg["mode"] == "h":
        ff("-ss", str(seg["start"]), "-t", str(seg["dur"]), "-i", s,
           "-vf", f"scale={w}:{h}:flags=lanczos,fps=30,format=yuv420p",
           "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", out)
    else:
        th = int(h * 0.9) // 2 * 2; tw = int(th * 9 / 16) // 2 * 2
        mask = os.path.join(TMP, f"mask_{tw}x{th}.png"); phone_mask(tw, th, int(tw * 0.08), mask)
        fc = (f"[0:v]fps=30,split[a][b];"
              f"[a]scale={w}:-2,crop={w}:{h},boxblur=24:4,eq=brightness=-0.32:saturation=0.8[bg];"
              f"[b]scale={tw}:{th}:flags=lanczos,format=rgba[fg0];[1:v]format=gray[m];[fg0][m]alphamerge[fg];"
              f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")
        ff("-ss", str(seg["start"]), "-t", str(seg["dur"]), "-i", s, "-loop", "1", "-i", mask,
           "-filter_complex", fc, "-map", "[v]", "-t", str(seg["dur"]),
           "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", out)

def frame(src, t, out, vf=None):
    args = ["-ss", f"{t:.2f}", "-i", src, "-frames:v", "1"]
    if vf: args += ["-vf", vf]
    ff(*args, out)

def webp_variants(img_path, name, widths, quality=78, crop=None):
    im = Image.open(img_path)
    im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") and "A" in im.getbands() or im.mode == "P" else im.convert("RGB")
    if crop: im = im.crop(crop)
    made = []
    for w in widths:
        if w > im.width: continue
        h = round(im.height * w / im.width)
        r = im.resize((w, h), Image.LANCZOS)
        p = os.path.join(OUT, f"{name}-{w}.webp"); r.save(p, "WEBP", quality=quality, method=6); made.append((w, h, p))
    return made

def check():
    rows = []
    for seg in SEGMENTS:
        p = os.path.join(TMP, f"seg_{seg['id']}.mp4"); segment(seg, p)
        tiles = []
        for k, t in enumerate([0.1, seg["dur"] / 2, seg["dur"] - 0.15]):
            f = os.path.join(TMP, f"chk_{seg['id']}_{k}.png"); frame(p, t, f, "scale=320:-2"); tiles.append(Image.open(f))
        rows.append(tiles)
    sheet = Image.new("RGB", (960, 180 * len(rows)))
    for i, r in enumerate(rows):
        for j, im in enumerate(r): sheet.paste(im, (j * 320, i * 180))
    sheet.save("/home/claude/assets/sheets/reel_check.jpg", quality=85); print("sheet ok")

def build():
    meta = {}
    # 1. reel
    parts = []
    for seg in SEGMENTS:
        p = os.path.join(TMP, f"seg_{seg['id']}.mp4"); segment(seg, p); parts.append(p)
    lst = os.path.join(TMP, "reel.txt")
    open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    full = os.path.join(TMP, "reel_full.mp4")
    ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", full)
    for w, h, crf in [(1280, 720, 27), (640, 360, 28)]:
        ff("-i", full, "-vf", f"scale={w}:{h}:flags=lanczos", "-an", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", str(crf), "-profile:v", "high", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           os.path.join(OUT, f"reel-{w}.mp4"))
    frame(full, 0.2, os.path.join(TMP, "reel_poster.png"))
    webp_variants(os.path.join(TMP, "reel_poster.png"), "reel-poster", [1280, 640], quality=74)
    t = 0.0; cues = []
    for seg in SEGMENTS: cues.append(dict(id=seg["id"], start=round(t, 2), end=round(t + seg["dur"], 2))); t += seg["dur"]
    meta["reel_cues"] = cues
    # 2. card previews (640x360 loops) from the same segments
    for seg, p in zip(SEGMENTS, parts):
        ff("-i", p, "-vf", "scale=640:360:flags=lanczos", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "29",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", os.path.join(OUT, f"preview-{seg['id']}.mp4"))
    # 3. stills
    stills = [
        ("still-tsp-infinity", "tsp_infinity_reveal.mp4", 4.4, None, [1440, 960, 640]),
        ("still-tsp-mandelbrot", "tsp_mandelbrot.mp4", 183.0, None, [1440, 960, 640]),
        ("still-sienna-board", "sienna_morphy_169.mp4", 8.0, None, [1440, 960, 640]),
        ("still-lights-scene", "lights_ep1.mp4", 186.0, None, [1440, 960, 640]),
        ("still-tsp-short", "tsp_hexagon_short.mp4", 12.0, None, [720, 540, 360]),
        ("still-wvhh-jackie", "wvhh_jackie_raw2.mp4", 2.4, None, [720, 540, 360]),
    ]
    for name, src, tt, vf, widths in stills:
        f = os.path.join(TMP, f"{name}.png"); frame(os.path.join(SRC, src), tt, f, vf)
        meta[name] = [dict(w=w, h=h) for w, h, _ in webp_variants(f, name, widths)]
    images = [
        ("still-lights-thumb", "/mnt/user-data/uploads/LIGHTS ON/Episode 1/Lights_On_Ep1_thumbnail_v2.png", [1280, 960, 640], None),
        ("still-wvhh-phone", os.path.join(SRC, "wvhh_e01_s01.png"), [720, 540, 360], None),
        ("still-sienna-portrait", "/mnt/user-data/uploads/CHESS LESSON/Sienna_Headshot_Anchor.jpg", [800, 480], None),
    ]
    for name, path, widths, crop in images:
        meta[name] = [dict(w=w, h=h) for w, h, _ in webp_variants(path, name, widths, crop=crop)]
    # 4. playable clips for the case study (with sound, click to play)
    ff("-i", os.path.join(SRC, "tsp_hexagon_short.mp4"), "-vf", "scale=720:1280:flags=lanczos", "-c:v", "libx264",
       "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
       os.path.join(OUT, "clip-tsp-short.mp4"))
    frame(os.path.join(SRC, "tsp_hexagon_short.mp4"), 22.0, os.path.join(TMP, "clip-tsp-short.png"))
    webp_variants(os.path.join(TMP, "clip-tsp-short.png"), "clip-tsp-short-poster", [720, 360])
    # opening of the Mandelbrot film, with sound, ending in the pause as the equation lands
    ff("-ss", "0", "-t", "29.6", "-i", os.path.join(SRC, "tsp_mandelbrot.mp4"), "-vf", "scale=1280:720:flags=lanczos",
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
       "-af", "afade=t=out:st=29.0:d=0.6", "-movflags", "+faststart", os.path.join(OUT, "clip-tsp-mandelbrot.mp4"))
    frame(os.path.join(SRC, "tsp_mandelbrot.mp4"), 24.8, os.path.join(TMP, "clip-tsp-mandelbrot.png"))
    webp_variants(os.path.join(TMP, "clip-tsp-mandelbrot.png"), "clip-tsp-mandelbrot-poster", [1280, 640])
    json.dump(meta, open(os.path.join(OUT, "media.json"), "w"), indent=1)
    print(json.dumps(meta["reel_cues"]))

if __name__ == "__main__":
    {"check": check, "build": build}[sys.argv[1]]()
