#!/usr/bin/env bash
# Analyzer: install the Claude Code skill on this computer (Mac or Linux). Safe to run again.
set -euo pipefail
cd "$(dirname "$0")"
DEST="$HOME/.claude/skills/analyzer"

echo "1/4 Copying the skill to $DEST"
mkdir -p "$DEST"
cp -R skills/analyzer/. "$DEST/"

echo "2/4 Checking ffmpeg"
if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then brew install ffmpeg
  elif command -v apt-get >/dev/null 2>&1; then sudo apt-get install -y ffmpeg
  else echo "Please install ffmpeg (https://ffmpeg.org/download.html), then run this again."; exit 1; fi
fi

echo "3/4 Checking uv (the Python installer)"
if ! command -v uv >/dev/null 2>&1; then
  export PATH="$HOME/.local/bin:$PATH"
  command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "4/4 Installing the speech model runtime and video tools (about 1-2 minutes)"
uv venv --quiet --allow-existing --python 3.12 "$DEST/.venv"
uv pip install --quiet --python "$DEST/.venv/bin/python" "faster-whisper>=1.1" "opencv-python-headless>=4.9,<5" "pillow>=10.3" "numpy>=1.26" "yt-dlp>=2025.1"

echo
echo "Analyzer is installed. Open Claude Code, paste a reel link and say: analyze this."
