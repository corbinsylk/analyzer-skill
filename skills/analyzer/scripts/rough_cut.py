"""Build a rough cut from the user's own footage: the takes Claude chose, in script order, cut tight on word edges,
reframed to 9:16 on the face, with word-by-word captions.

usage: rough_cut.py FOOTAGE FOOTAGE_WORKDIR [--out rough-cut.mp4] [--no-captions]

Reads FOOTAGE_WORKDIR/words.json (transcribe.py on the footage) and FOOTAGE_WORKDIR/keep.json, written by Claude:
  [{"line": "the script line this take covers", "start": 12.4, "end": 15.9}, ...]   in the order they play
"""
import argparse, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import clipkit as K  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("footage")
    ap.add_argument("workdir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--text-color", default="#F5F1EA")
    ap.add_argument("--active-color", default="#B03926")
    ap.add_argument("--no-captions", action="store_true")
    a = ap.parse_args()
    words = json.load(open(os.path.join(a.workdir, "words.json")))
    keep = json.load(open(os.path.join(a.workdir, "keep.json")))
    info = K.video_info(a.workdir, a.footage)
    out = a.out or os.path.join(a.workdir, "rough-cut.mp4")
    with tempfile.TemporaryDirectory() as tmp:
        parts, timeline, t = [], [], 0.0
        for i, k in enumerate(keep):
            s, e, inside = K.snap(words, float(k["start"]), float(k["end"]))
            e = min(e, inside[-1]["e"] + 0.3)          # the speech model often ends a last word early: a short tail keeps it whole
            fx, gaps, _, _ = K.face_track(a.footage, s, e, info)
            p = os.path.join(tmp, f"p{i:03d}.mp4")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", a.footage,
                            "-filter_complex", K.picture_graph(info, fx, gaps) + ";[v]format=yuv420p[o]", "-map", "[o]", "-map", "0:a?",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-r", "30", "-c:a", "aac", "-ar", "48000", "-b:a", "192k", p],
                           check=True)
            parts.append(p)
            for w in inside:
                timeline.append({"w": w["w"], "s": w["s"] - s + t, "e": w["e"] - s + t})
            t += e - s
            print(f"  take {i + 1}/{len(keep)}: {k.get('line', '')[:60]}", flush=True)
        lst = os.path.join(tmp, "parts.txt")
        open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
        joined = os.path.join(tmp, "joined.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined], check=True)
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", joined]
        if a.no_captions:
            cmd += ["-map", "0:v", "-map", "0:a?", "-c:v", "copy"]
        else:
            caps = K.caption_track(timeline, 0.0, t, tmp, K.hex_rgb(a.text_color), K.hex_rgb(a.active_color))
            cmd += ["-f", "concat", "-safe", "0", "-i", caps, "-filter_complex",
                    "[1:v]format=rgba[c];[0:v][c]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[o]",
                    "-map", "[o]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "18"]
        cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
        subprocess.run(cmd, check=True)
    every = max(0.5, t / 8)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", f"fps=1/{every:.3f},scale=270:-2,tile=8x1", "-frames:v", "1",
                    os.path.splitext(out)[0] + ".jpg"], check=True)
    print(f"Done: {out} ({t:.1f} s, {len(keep)} takes)")


if __name__ == "__main__":
    sys.exit(main())
