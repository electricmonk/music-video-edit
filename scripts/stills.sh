#!/bin/zsh
# Grid of stills at given times, for contact sheets (one frame per shot) and render verification.
# usage: stills.sh VIDEO OUT.jpg [--width 270] [--cols N] [--vf PREFILTER] T1 T2 ...
#   times in seconds of VIDEO; --vf is applied before scaling (e.g. a crop to preview framing).
# Prints the time of each tile, left-to-right, top-to-bottom.
set -e
V=$1; OUT=$2; shift 2
W=270; COLS=0; VF=""
while [[ $1 == --* ]]; do
  case $1 in --width) W=$2;; --cols) COLS=$2;; --vf) VF="$2,";; esac; shift 2
done
(( $# )) || { echo "no times given"; exit 1; }
(( COLS )) || COLS=$(( $# < 6 ? $# : 6 ))
ROWS=$(( ($# + COLS - 1) / COLS ))
T=$(mktemp -d); i=0
for t in "$@"; do
  i=$((i+1)); ffmpeg -v error -y -ss $t -i "$V" -frames:v 1 -vf "${VF}scale=$W:-2" $T/s$(printf %03d $i).png
  echo "$i: $t s"
done
ffmpeg -v error -y -i $T/s%03d.png -vf "tile=${COLS}x${ROWS}:padding=4:color=white" -frames:v 1 "$OUT"
echo "grid: $OUT (${COLS}x${ROWS})"
