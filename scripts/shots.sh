#!/bin/zsh
# usage: shots.sh video START DUR [threshold=5]  -> prints cut times (relative to START) and scores
ffmpeg -hide_banner -ss $2 -t $3 -i "$1" -vf "scale=480:270,scdet=threshold=${4:-5}" -an -f null - 2>&1 \
  | grep -o "lavfi.scd.score: [0-9.]*\|lavfi.scd.time: [0-9.]*" | paste - - | awk '{print "cut", $4, "score", $2}'
