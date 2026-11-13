# Analyzer

A Claude Code skill. Give it a reel you like and it breaks down the hook, the pacing and the editing. Then it reuses
the same structure to build a video around your topic.

- **The breakdown.** Every cut found and measured, one frame per shot, the words over each shot, and the numbers: shot
  length, cuts in the first 3 seconds, words per minute. Claude looks at the frames and writes up the hook, the
  structure beat by beat, the pacing and the editing (framing, zooms, text on screen, captions, B-roll), and the formula
  as a fill-in template.
- **The remake.** Tell it your topic and it writes your script word for word in the same structure and length, with a
  shot plan and the on-screen text for every beat.
- **The rough cut.** Film the script, drag in your footage, and it picks your best take of every line and cuts them
  together tight, framed 9:16 on your face, with word-by-word captions.
- **Runs on your computer.** Links download without a login; transcription is local. No API keys.

## Install (one time)

You need a Mac (or Linux) and Claude Code. Paste this into Claude Code:

```
Install the Analyzer skill: clone https://github.com/corbinsylk/analyzer-skill into my home folder and run bash install.sh inside it.
```

Or in Terminal:

```bash
git clone https://github.com/corbinsylk/analyzer-skill ~/analyzer-skill && bash ~/analyzer-skill/install.sh
```

## Use

Open Claude Code and say:

```
analyze this https://www.instagram.com/reel/...
```

Then: "remake it for my topic: ...". After filming, drag in your footage: "make the rough cut".

Everything lands in a folder next to the video called `<video name>-analysis/`: `breakdown.md`, `remake.md`,
`pacing.md`, contact sheets of every shot, and `rough-cut.mp4`. Downloaded reels are saved in `~/Movies/Analyzer/`.

## What it runs

yt-dlp (downloads), faster-whisper (transcript with word times), ffmpeg (cuts and encoding), OpenCV (face framing),
Plus Jakarta Sans ExtraBold for captions (SIL Open Font License, `skills/analyzer/fonts/OFL.txt`).

Only analyse and remake videos you are allowed to use as a reference; the remake copies a structure, never the words.

## Update

```bash
cd ~/analyzer-skill && git pull && bash install.sh
```
