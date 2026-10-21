#!/bin/zsh
# Idempotent setup for the music-video-edit skill.
set -e
MV=~/.cache/music-video-edit; SK=${0:A:h}
mkdir -p $MV/fonts $MV/bin
command -v ffmpeg >/dev/null || { echo "ffmpeg missing: brew install ffmpeg"; exit 1; }
if [ ! -x $MV/venv/bin/python ]; then python3 -m venv $MV/venv; fi
$MV/venv/bin/python -c "import librosa, demucs, whisper, matplotlib, soundfile" 2>/dev/null || \
  $MV/venv/bin/pip install -q librosa demucs openai-whisper matplotlib soundfile
for p in heebo/Heebo%5Bwght%5D assistant/Assistant%5Bwght%5D rubik/Rubik%5Bwght%5D \
  frankruhllibre/FrankRuhlLibre%5Bwght%5D notosanshebrew/NotoSansHebrew%5Bwdth,wght%5D \
  notoserifhebrew/NotoSerifHebrew%5Bwdth,wght%5D davidlibre/DavidLibre-Medium varelaround/VarelaRound-Regular \
  secularone/SecularOne-Regular suezone/SuezOne-Regular karantina/Karantina-Regular; do
  f=$MV/fonts/$(basename $p | sed 's/%5B/[/g; s/%5D/]/g').ttf
  [ -s "$f" ] || curl -sfL --max-time 60 -o "$f" "https://github.com/google/fonts/raw/main/ofl/$p.ttf" || echo "font fetch failed: $p"
done
for t in caption faces; do
  if [ ! -x $MV/bin/$t ] || [ $SK/$t.swift -nt $MV/bin/$t ]; then
    swiftc -O -o $MV/bin/$t $SK/$t.swift 2>&1 | grep -E "error|license" && { echo "swiftc failed (Xcode license? run: sudo xcodebuild -license)"; exit 1; }
  fi
done
echo "ready: $MV"
