"""Transcribe a video on this computer, with a time for every word. No API key, nothing uploaded.

usage: transcribe.py VIDEO WORKDIR [--model small]

Writes into WORKDIR:
  words.json       every word: {"w": text, "s": start seconds, "e": end seconds}
  transcript.md    the talk in short timed lines, for Claude to read and pick moments from
  video.json       duration, width and height as the video plays (rotation applied)
"""
import argparse, json, os, subprocess, sys


def probe(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:stream_side_data=rotation:format=duration", "-of", "json", video],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    st = d["streams"][0]
    w, h = st["width"], st["height"]
    rot = 0
    for sd in st.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    if abs(rot) % 180 == 90:
        w, h = h, w
    return {"duration": float(d["format"]["duration"]), "width": w, "height": h}


def stamp(t):
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:04.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("workdir", nargs="?", help="default: <video name>-analysis beside the video")
    ap.add_argument("--model", default="small", help="tiny, base, small (default), medium or large-v3: bigger is slower and more accurate")
    ap.add_argument("--language", default=None, help="for example en; empty = detect")
    a = ap.parse_args()
    a.workdir = a.workdir or os.path.splitext(a.video)[0] + "-analysis"
    print(f"Work folder: {a.workdir}", flush=True)
    os.makedirs(a.workdir, exist_ok=True)
    info = probe(a.video)
    json.dump(info, open(os.path.join(a.workdir, "video.json"), "w"), indent=1)

    import logging, warnings
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    warnings.filterwarnings("ignore")
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("faster_whisper").setLevel(logging.ERROR)
    import numpy as np
    from faster_whisper import WhisperModel
    # the audio as 16 kHz mono samples, read by ffmpeg (no other audio library needed)
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", a.video, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    wav = np.frombuffer(pcm, np.float32)
    print(f"Transcribing {stamp(info['duration'])} of audio with the '{a.model}' model (the first run downloads it once)...", flush=True)
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(wav, word_timestamps=True, vad_filter=True, language=a.language)
    words, lines, last = [], [], 0.0
    for seg in segments:
        seg_words = [w for w in (seg.words or []) if w.word.strip()]
        for w in seg_words:
            words.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)})
        if seg_words:
            lines.append(f"[{stamp(seg_words[0].start)} - {stamp(seg_words[-1].end)}] {seg.text.strip()}")
        if seg.end - last >= 60:
            last = seg.end
            print(f"  {stamp(seg.end)} of {stamp(info['duration'])} done", flush=True)
    json.dump(words, open(os.path.join(a.workdir, "words.json"), "w"), indent=0)
    head = (f"# Transcript\n\nVideo: {os.path.basename(a.video)} · {stamp(info['duration'])} · {info['width']}x{info['height']}\n"
            f"Times are minutes:seconds from the start of the video.\n\n")
    open(os.path.join(a.workdir, "transcript.md"), "w").write(head + "\n".join(lines) + "\n")
    print(f"\nDone: {len(words)} words -> {os.path.join(a.workdir, 'transcript.md')}")


if __name__ == "__main__":
    sys.exit(main())
