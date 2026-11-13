"""Get the reel to analyse: download a link (Instagram, TikTok, YouTube Shorts, X...) or use a file on this computer.

usage: fetch.py LINK_OR_FILE [--out FOLDER]
Prints the path of the video on the last line. Downloads go to ~/Movies/Analyzer/ unless --out is given.
"""
import argparse, glob, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", default=os.path.expanduser("~/Movies/Analyzer"))
    a = ap.parse_args()
    src = a.source.strip().strip('"').strip("'")
    if os.path.exists(src):
        print(os.path.abspath(src))
        return
    if not re.match(r"https?://", src):
        raise SystemExit(f"Not a file on this computer and not a link: {src}")
    os.makedirs(a.out, exist_ok=True)
    ytdlp = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
    # plain download, no browser cookies: works for public posts
    tpl = os.path.join(a.out, "%(extractor)s-%(id)s.%(ext)s")
    r = subprocess.run([ytdlp, "--no-playlist", "-f", "bv*+ba/b", "--merge-output-format", "mp4", "-o", tpl,
                        "--print", "after_move:filepath", "--no-simulate", "--quiet", "--no-warnings", src],
                       capture_output=True, text=True)
    path = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode != 0 or not os.path.exists(path):
        msg = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["unknown error"]
        raise SystemExit("Could not download that link: " + msg[0] +
                         "\nIf the post is private or age-restricted, download it yourself (or screen-record it) and drag the file in.")
    print(path)


if __name__ == "__main__":
    sys.exit(main())
