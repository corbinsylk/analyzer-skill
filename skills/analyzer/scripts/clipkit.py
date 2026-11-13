"""Cut the chosen moments into vertical 9:16 clips with word-by-word captions, ready to post.

usage: make_clips.py VIDEO WORKDIR [--text-color "#F5F1EA"] [--active-color "#B03926"] [--no-captions]

Reads WORKDIR/moments.json (written by Claude) and WORKDIR/words.json (from transcribe.py):
  [{"title": "...", "start": 63.2, "end": 101.8, "score": 8, "hook": "...", "why": "..."}, ...]
Writes WORKDIR/clips/NN-title.mp4 (1080x1920, H.264, sound levelled), a still of each clip for a quick
check (NN-title.jpg) and WORKDIR/clips/scores.md.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "..", "fonts", "PlusJakartaSans.ttf")
W, H = 1080, 1920
CAP_Y = 1360          # the caption line's centre: under the chin, above the app's buttons and description (safe to y 1500)
CAP_SIZE = 84
CAP_MAX_W = 860       # keep captions inside x 110-970
MAX_WORDS, MAX_CHARS, PAUSE = 3, 20, 0.45


def run(cmd):
    subprocess.run(cmd, check=True)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48] or "clip"


def video_info(workdir, video):
    p = os.path.join(workdir, "video.json")
    if os.path.exists(p):
        return json.load(open(p))
    sys.path.insert(0, HERE)
    from transcribe import probe
    return probe(video)


# ------------------------------------------------------------------ where the face is
def face_track(video, start, end, info):
    """Look for the speaker's face twice a second. Returns the face centre (0-1 across the frame, the median: one
    steady crop, like an editor would set) and the stretches with no face (B-roll, graphics, screens), clip-relative."""
    import cv2
    det = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
    sw = 480
    sh = int(round(info["height"] * sw / info["width"] / 2) * 2)
    step = 0.5
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", video,
                          "-vf", f"fps={1 / step},scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    n = len(raw) // (sw * sh)
    xs, hit = [], []
    for k in range(n):
        img = np.frombuffer(raw[k * sw * sh:(k + 1) * sw * sh], np.uint8).reshape(sh, sw)
        faces = det.detectMultiScale(img, scaleFactor=1.1, minNeighbors=6, minSize=(sw // 14, sw // 14))
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            xs.append((x + w / 2) / sw)
        hit.append(bool(len(faces)))
    # a single missed check inside a talking-head stretch is the detector blinking, not a cutaway: fill it
    for k in range(1, len(hit) - 1):
        if not hit[k] and hit[k - 1] and hit[k + 1]:
            hit[k] = True
    gaps, k = [], 0
    while k < len(hit):
        if not hit[k]:
            j = k
            while j < len(hit) and not hit[j]:
                j += 1
            if (j - k) * step >= 1.0:                       # cutaways of a second or more
                gaps.append((max(0.0, k * step - step / 2), j * step - step / 2))
            k = j
        else:
            k += 1
    return (float(np.median(xs)) if xs else 0.5), gaps, sum(hit), len(hit)


def crop_filter(info, fx):
    w, h = info["width"], info["height"]
    if w / h <= 9 / 16 + 0.01:                     # already vertical: fill the frame
        return f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
    cw = int(h * 9 / 16) // 2 * 2
    x = int(min(max(fx * w - cw / 2, 0), w - cw))
    return f"crop={cw}:{h}:{x}:0,scale={W}:{H},setsar=1"


def picture_graph(info, fx, gaps):
    """The clip's picture as a filter graph from [0:v] to [v]: the face crop, and where there is no face in a wide
    video (graphics, screens, B-roll) the whole frame shown on a blurred fill of itself, so nothing gets cut off."""
    crop = crop_filter(info, fx)
    wide = info["width"] / info["height"] > 9 / 16 + 0.01
    if not wide or not gaps:
        return f"[0:v]{crop}[v]"
    on = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in gaps)
    return (f"[0:v]split=3[a][b][c];[a]{crop}[cr];"
            f"[b]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:2,eq=brightness=-0.08[bg];"
            f"[c]scale={W}:-2[fg];[bg][fg]overlay=0:(H-h)/2[fit];"
            f"[cr][fit]overlay=0:0:enable='{on}',setsar=1[v]")


# ------------------------------------------------------------------ captions
def pages(words):
    out, cur = [], []
    for i, w in enumerate(words):
        if cur:
            gap = w["s"] - cur[-1]["e"]
            text = " ".join(x["w"] for x in cur + [w])
            if len(cur) >= MAX_WORDS or len(text) > MAX_CHARS or gap > PAUSE or re.search(r"[.!?]$", cur[-1]["w"]):
                out.append(cur)
                cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def font(size):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_name("ExtraBold")
    except Exception:
        pass
    return f


def draw_page(page, active, text_rgb, active_rgb):
    size = CAP_SIZE
    words = [w["w"] for w in page]
    while True:
        f = font(size)
        space = f.getlength(" ")
        widths = [f.getlength(t) for t in words]
        total = sum(widths) + space * (len(words) - 1)
        if total <= CAP_MAX_W or size <= 44:
            break
        size -= 4
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d, ds = ImageDraw.Draw(img), ImageDraw.Draw(shadow)
    x = (W - total) / 2
    asc, desc = f.getmetrics()
    y = CAP_Y - (asc + desc) / 2
    for i, (t, wd) in enumerate(zip(words, widths)):
        ds.text((x, y + 5), t, font=f, fill=(0, 0, 0, 170), stroke_width=6, stroke_fill=(0, 0, 0, 170))
        d.text((x, y), t, font=f, fill=active_rgb + (255,) if i == active else text_rgb + (255,),
               stroke_width=4, stroke_fill=(18, 14, 12, 235))   # a thin dark edge: every word reads on light and dark footage
        x += wd + space
    shadow = shadow.filter(ImageFilter.GaussianBlur(9))
    return Image.alpha_composite(shadow, img)


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def caption_track(words, start, end, tmp, text_rgb, active_rgb):
    """A list of caption images with how long each shows (ffmpeg concat format), times relative to the clip start."""
    blank = os.path.join(tmp, "blank.png")
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
    events = []                                   # (t0, t1, file)
    for p_i, page in enumerate(pages(words)):
        for a_i, w in enumerate(page):
            t0 = w["s"] - start
            t1 = (page[a_i + 1]["s"] if a_i + 1 < len(page) else page[-1]["e"] + 0.15) - start
            png = os.path.join(tmp, f"c{p_i:04d}_{a_i}.png")
            draw_page(page, a_i, text_rgb, active_rgb).save(png)
            events.append((max(0.0, t0), max(0.0, t1), png))
    lines, t = ["ffconcat version 1.0"], 0.0
    dur = end - start
    for t0, t1, png in events:
        t0, t1 = max(t0, t), min(t1, dur)
        if t1 <= t0:
            continue
        if t0 > t + 0.001:
            lines += [f"file '{blank}'", f"duration {t0 - t:.3f}"]
        lines += [f"file '{png}'", f"duration {t1 - t0:.3f}"]
        t = t1
    lines += [f"file '{blank}'", f"duration {max(0.04, dur - t):.3f}", f"file '{blank}'"]
    lst = os.path.join(tmp, "captions.txt")
    open(lst, "w").write("\n".join(lines) + "\n")
    return lst


# ------------------------------------------------------------------ one clip
def snap(words, start, end):
    """The clip's edges on word boundaries: from the first word starting at `start` (0.05 s grace) to the last word
    ending at `end`. The lead-in and the tail never reach into a neighbouring word, so no stray syllable leaks in."""
    idx = [i for i, w in enumerate(words) if w["s"] >= start - 0.05 and w["e"] <= end + 0.05]
    if not idx:
        raise SystemExit(f"No words between {start} and {end}: check the times against words.json")
    i0, i1 = idx[0], idx[-1]
    prev_end = words[i0 - 1]["e"] if i0 > 0 else 0.0
    next_start = words[i1 + 1]["s"] if i1 + 1 < len(words) else words[i1]["e"] + 1.0
    s = max(prev_end + 0.02, words[i0]["s"] - 0.08, 0.0)
    e = min(next_start - 0.02, words[i1]["e"] + 0.3)
    return s, max(e, words[i1]["e"] + 0.02), words[i0:i1 + 1]


def make_clip(video, info, words, m, n, outdir, a):
    start, end, inside = snap(words, float(m["start"]), float(m["end"]))
    fx, gaps, found, tried = face_track(video, start, end, info)
    name = f"{n:02d}-{slug(m['title'])}"
    out = os.path.join(outdir, name + ".mp4")
    graph = picture_graph(info, fx, gaps)
    with tempfile.TemporaryDirectory() as tmp:
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", video]
        if a.no_captions:
            cmd += ["-filter_complex", graph + ";[v]format=yuv420p[o]", "-map", "[o]", "-map", "0:a?"]
        else:
            lst = caption_track(inside, start, end, tmp, hex_rgb(a.text_color), hex_rgb(a.active_color))
            cmd += ["-f", "concat", "-safe", "0", "-i", lst,
                    "-filter_complex", graph + ";[1:v]format=rgba[c];[v][c]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[o]",
                    "-map", "[o]", "-map", "0:a?"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
        run(cmd)
    # a contact sheet: 8 frames across the clip, to check framing and captions over its whole length
    every = max(0.5, (end - start) / 8)
    run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", f"fps=1/{every:.3f},scale=270:-2,tile=8x1", "-frames:v", "1",
         os.path.join(outdir, name + ".jpg")])
    return {"file": name + ".mp4", "start": start, "end": end, "len": end - start, "face": f"{found}/{tried}",
            "cutaways": len(gaps), **m}


def stamp(t):
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:04.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("workdir", nargs="?", help="default: <video name>-clips beside the video")
    ap.add_argument("--text-color", default="#F5F1EA")
    ap.add_argument("--active-color", default="#B03926", help="the colour of the word being said")
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--only", type=int, default=0, help="remake just clip number N")
    a = ap.parse_args()
    a.workdir = a.workdir or os.path.splitext(a.video)[0] + "-clips"
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} is not installed. Run the Clipper install again.")
    words = json.load(open(os.path.join(a.workdir, "words.json")))
    moments = json.load(open(os.path.join(a.workdir, "moments.json")))
    info = video_info(a.workdir, a.video)
    outdir = os.path.join(a.workdir, "clips")
    os.makedirs(outdir, exist_ok=True)
    done = []
    for n, m in enumerate(moments, 1):
        if a.only and n != a.only:
            continue
        print(f"Clip {n}/{len(moments)}: {m['title']} ...", flush=True)
        done.append(make_clip(a.video, info, words, m, n, outdir, a))
    rows = ["# Clips", "", f"From: {os.path.basename(a.video)}", "",
            "| # | Clip | From | Length | Score | Why it works |", "|---|---|---|---|---|---|"]
    for n, c in enumerate(done, 1):
        rows.append(f"| {n} | {c['file']} | {stamp(c['start'])} | {c['len']:.0f} s | {c.get('score', '')}/10 | {c.get('why', '')} |")
    rows += ["", "## Hooks and post captions", ""]
    for c in done:
        cap = "\n".join("  " + line for line in str(c.get("caption", "")).splitlines())
        rows += [f"**{c['title']}** ({c['file']})", "", f"- Opening line: {c.get('hook', '')}", "- Post caption:", "", cap, ""]
    if not a.only:
        open(os.path.join(outdir, "scores.md"), "w").write("\n".join(rows) + "\n")
    for c in done:
        print(f"  {c['file']}  {c['len']:.0f} s  face in {c['face']} checks, {c['cutaways']} cutaway(s) shown whole")
    print(f"Done: {outdir}")


if __name__ == "__main__":
    sys.exit(main())
