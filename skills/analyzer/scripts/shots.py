"""Measure a reel's editing: every cut, one frame per shot, and the pacing in numbers.

usage: shots.py VIDEO [WORKDIR] [--threshold 0.28]

Needs WORKDIR/words.json from transcribe.py for the talking numbers (run that first). Writes into WORKDIR:
  shots.json       every shot: start, end, length, its frame
  shots/NN.jpg     one frame from the middle of each shot (and NN-a/NN-b at its start and end for shots over 2 s)
  sheet-N.jpg      contact sheets of the shots, numbered, 6 across, for Claude to look at
  pacing.md        the numbers: shots, average and median shot length, cuts in the first 3 s, the pacing over time,
                   words per minute, the hook's words, and a shot-by-shot table with what was being said
"""
import argparse, json, os, re, subprocess, sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "..", "fonts", "PlusJakartaSans.ttf")


def duration(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def cuts(video, threshold):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-an", "-vf", f"select='gt(scene,{threshold})',showinfo",
                        "-f", "null", "-"], capture_output=True, text=True)
    ts = [float(m.group(1)) for m in re.finditer(r"pts_time:([0-9.]+)", r.stderr)]
    out = []
    for t in ts:                                     # flashes and fast whips fire twice: keep cuts at least 0.15 s apart
        if not out or t - out[-1] >= 0.15:
            out.append(t)
    return out


def join_words(ws):
    """Words back into text: "80", "-90", "%" -> "80-90%"."""
    out = ""
    for w in ws:
        out += w if (not out or re.match(r"^[-%,.!?;:')\]]", w) or out.endswith(("-", "(", "$"))) else " " + w
    return out


def grab(video, t, path, w=720):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, t):.3f}", "-i", video, "-frames:v", "1",
                    "-vf", f"scale={w}:-2", "-q:v", "4", path], check=True)


def sheet(paths, labels, out, cols=6):
    ims = [Image.open(p).convert("RGB") for p in paths]
    ims = [im.resize((360, round(im.height * 360 / im.width))) for im in ims]
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    S = Image.new("RGB", (cols * w, rows * (h + 34)), (20, 20, 20))
    d = ImageDraw.Draw(S)
    f = ImageFont.truetype(FONT, 22)
    for i, (im, lab) in enumerate(zip(ims, labels)):
        x, y = (i % cols) * w, (i // cols) * (h + 34)
        S.paste(im, (x, y + 34))
        d.text((x + 8, y + 5), lab, font=f, fill=(240, 240, 240))
    S.save(out, quality=85)


def stamp(t):
    m, s = divmod(round(t, 1), 60)
    return f"{int(m):02d}:{s:04.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("workdir", nargs="?")
    ap.add_argument("--threshold", type=float, default=0.28, help="lower finds softer cuts, higher ignores fast motion")
    a = ap.parse_args()
    wd = a.workdir or os.path.splitext(a.video)[0] + "-analysis"
    os.makedirs(os.path.join(wd, "shots"), exist_ok=True)
    dur = duration(a.video)
    cs = [t for t in cuts(a.video, a.threshold) if 0.1 < t < dur - 0.1]
    bounds = [0.0] + cs + [dur]
    words = json.load(open(os.path.join(wd, "words.json"))) if os.path.exists(os.path.join(wd, "words.json")) else []

    shots, paths, labels = [], [], []
    for i in range(len(bounds) - 1):
        s, e = bounds[i], bounds[i + 1]
        n = i + 1
        mid = os.path.join(wd, "shots", f"{n:02d}.jpg")
        grab(a.video, (s + e) / 2, mid)
        frames = [f"shots/{n:02d}.jpg"]
        if e - s > 2.0:                                # long shots: also their first and last moment (zooms, text builds)
            for tag, t in (("a", s + 0.15), ("b", e - 0.2)):
                grab(a.video, t, os.path.join(wd, "shots", f"{n:02d}-{tag}.jpg"))
                frames.append(f"shots/{n:02d}-{tag}.jpg")
        said = join_words([w["w"] for w in words if s <= (w["s"] + w["e"]) / 2 < e])   # each word in one shot only
        shots.append({"n": n, "start": round(s, 2), "end": round(e, 2), "len": round(e - s, 2), "frames": frames, "said": said})
        paths.append(mid)
        labels.append(f"{n}  {stamp(s)}  {e - s:.1f}s")
    for k in range(0, len(paths), 36):
        sheet(paths[k:k + 36], labels[k:k + 36], os.path.join(wd, f"sheet-{k // 36 + 1}.jpg"))
    json.dump(shots, open(os.path.join(wd, "shots.json"), "w"), indent=1)

    lens = sorted(x["len"] for x in shots)
    med = lens[len(lens) // 2]
    first3 = sum(1 for t in cs if t < 3.0)
    buckets = []
    for b0 in range(0, int(dur) + 1, 5):
        b1 = min(dur, b0 + 5)
        if b1 - b0 < 1:
            continue
        k = sum(1 for t in cs if b0 <= t < b1)
        buckets.append(f"| {stamp(b0)}-{stamp(b1)} | {k} | {'#' * k} |")
    talk = [w for w in words]
    wpm = (len(talk) / ((talk[-1]["e"] - talk[0]["s"]) / 60)) if len(talk) > 2 else 0
    hook = join_words([w["w"] for w in words if w["s"] < 3.0])
    first_word = words[0]["s"] if words else None
    md = [f"# Pacing: {os.path.basename(a.video)}", "",
          f"- Length: {dur:.1f} s",
          f"- Shots: {len(shots)} ({len(cs)} cuts), one every {dur / len(shots):.2f} s on average, median shot {med:.2f} s",
          f"- Shortest shot {lens[0]:.2f} s, longest {lens[-1]:.2f} s",
          f"- Cuts in the first 3 seconds: {first3}",
          f"- Talking: {len(words)} words, {wpm:.0f} words per minute" + (f", first word at {first_word:.2f} s" if words else " (no speech found)"),
          f"- Words in the first 3 seconds (the spoken hook): \"{hook}\"", "",
          "Cut detection counts hard cuts and big changes; a smooth zoom or a slow push is not a cut, so check the frames.", "",
          "## Cuts per 5 seconds", "", "| Time | Cuts | |", "|---|---|---|", *buckets, "",
          "## Shot by shot", "", "| # | From | Length | What is said | Frames |", "|---|---|---|---|---|"]
    md += [f"| {x['n']} | {stamp(x['start'])} | {x['len']:.2f} s | {x['said']} | {', '.join(x['frames'])} |" for x in shots]
    open(os.path.join(wd, "pacing.md"), "w").write("\n".join(md) + "\n")
    print(f"{len(shots)} shots, one every {dur / len(shots):.2f} s. Contact sheets: {wd}/sheet-*.jpg  Numbers: {wd}/pacing.md")


if __name__ == "__main__":
    sys.exit(main())
