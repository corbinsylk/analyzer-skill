---
name: analyzer
description: Break down a short-form video (a reel, TikTok or Short) the user likes, its hook, structure, pacing and editing, then reuse the same structure to write a new video on the user's own topic, and cut their footage into a rough cut. Use when the user pastes a reel link or drops a video and says "analyze this", "break this down", "why did this go viral", "what makes this work", "remake this for my topic", "/analyzer", or wants a script built on another video's structure.
---

# Analyzer

Give it a reel you like and it breaks down the hook, the pacing and the editing. Then it reuses the same structure to
build a video around your topic.

Everything runs on this computer. The tools live in `~/.claude/skills/analyzer/scripts/` and run with the skill's own
Python: `~/.claude/skills/analyzer/.venv/bin/python` (below: `PY` = that path, `AN` = `~/.claude/skills/analyzer/scripts`).

## 0. Check the install (every run)

```bash
test -x ~/.claude/skills/analyzer/.venv/bin/python && command -v ffmpeg
```
If either is missing, tell the user in one line and run the installer: `bash ~/analyzer-skill/install.sh`, or clone it
first: `git clone https://github.com/corbinsylk/analyzer-skill ~/analyzer-skill && bash ~/analyzer-skill/install.sh`.

## 1. Get the reel

A link (Instagram, TikTok, YouTube Shorts, X) or a file. Then:

```bash
PY AN/fetch.py "<link or file>"
```
It prints the video's path on its last line (downloads land in `~/Movies/Analyzer/`). Public posts download without a
login. If it fails (private, age-restricted, removed), tell the user to download or screen-record it and drag the file in.

## 2. Measure it

```bash
PY AN/transcribe.py "<video>"
PY AN/shots.py "<video>"
```
Both use the work folder `<video name>-analysis/` beside the video. transcribe.py gives `transcript.md` and `words.json`
(every word timed; a speed tip about "mps" on the first run is harmless). shots.py gives `pacing.md` (every number below, plus a shot-by-shot table with what is said over each
shot), `sheet-N.jpg` contact sheets (small, numbered, for the overview) and `shots/NN.jpg` (one frame per shot at 720 wide,
big enough to read text on screen; long shots also `NN-a`/`NN-b`, their first and last moment). If shots.py finds far fewer shots than the video obviously has, rerun with `--threshold 0.18`; if it splits
one shot into many (fast motion, flashes), use `--threshold 0.4`.

## 3. Look, then write the breakdown

Read `transcript.md` and `pacing.md`. Open every contact sheet for the overview, then open the `shots/NN.jpg` frames of
the first 3 seconds' shots and of any shot where something changes (text appears, a zoom, a graphic, a new location):
there is no need to open all of them. You cannot hear the video: say nothing about music or sound effects beyond what
the transcript shows. The transcript can mishear names and terms (a sport, a brand, a dish): check them against the
text on screen and use the right spelling in what you write.

Write `<work folder>/breakdown.md` with these sections, every claim tied to a time or a shot number:

1. **The hook (0-3 s).** The exact words, what is on screen (framing, text on screen and where it sits, movement), how
   many cuts, and why it stops the scroll: the curiosity gap, the promise, the pattern break.
2. **The structure.** The beats in order with their times: hook, setup or problem, the turns, the payoff, the call to
   action. For each beat: its job, its length in seconds and words, and the line that does the job.
3. **The pacing.** The numbers from pacing.md (shots, average and median shot length, cuts in the first 3 s, words per
   minute) and what they mean. To count a beat's words: `PY AN/words.py "<work folder>" <start> <end>` (seconds or
   minutes:seconds); it prints the word count, the pace and the words: where it speeds up, where it holds, how the cut rate follows the story.
4. **The editing.** Framing and camera (how much of the frame the face fills, zoom-ins, angle changes: by eye from the frames), on-screen text (style, size, position,
   when it appears), captions (style, how many words at a time), B-roll, screen recordings, graphics, transitions.
5. **The formula.** The structure as a fill-in template anyone could reuse: each beat as `[what goes here]` with its
   target length, word count and edit move.

Then tell the user the hook, the formula and the three things that make it work, in a few lines, and point to breakdown.md.

## 4. Remake it on the user's topic

Ask one question if they have not said it: "What topic (and who is it for) should I build the new video around?"
Then write `<work folder>/remake.md`:

- **The script, word for word**, beat by beat, in the same structure, each beat within about 10 % of the reference's
  word count (from words.py), so it runs the same length at the same pace. The hook uses the same mechanism as the
  reference (the same kind of promise, number, question or pattern break), never its words. If the user has told you
  how they talk (a voice or brand file, earlier scripts in this project, their own instructions), write in that voice;
  otherwise plain, direct and spoken, the way people talk to camera.
- **The shot plan**: for each beat, what to film (framing, where to look, gestures, props or locations), and the edit
  move at that moment taken from the reference (a cut, a zoom-in, text on screen with its exact words, B-roll to show).
- **On-screen text** listed separately, with its time.
- **Filming notes**: say every line twice so the best take can be picked; pause a second between lines.

## 5. Rough cut (when the user has filmed it)

When the user drags in their footage of the remake:

```bash
PY AN/transcribe.py "<footage>"
```
Read the footage's `transcript.md` and `words.json`. For each script line, pick the best clean take (complete, no
stumble; usually the last one), then write `<footage work folder>/keep.json`, in script order:

```json
[{"line": "the script line", "start": 12.40, "end": 15.92}]
```
`start` = the `s` of the take's first word, `end` = the `e` of its last word, from words.json. Then:

```bash
PY AN/rough_cut.py "<footage>" "<footage work folder>"
```
It cuts every take tight on its word edges, frames it 9:16 on the face, joins them in order with word-by-word captions,
and writes `rough-cut.mp4` plus `rough-cut.jpg` (8 frames across it). Open the jpg and check the face is framed and the
captions read. Tell the user what is in the rough cut and which edit moves from the shot plan they still add in their
editor (text, zooms, B-roll).
