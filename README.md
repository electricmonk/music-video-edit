# music-video-edit

A [Claude Code](https://claude.com/claude-code) skill for cutting music video clips on macOS with ffmpeg:

- audio snippets over a still cover image, and swapping a video's audio
- labelled comparison sheets (fonts, weights, outlines) and still grids for visual review
- musically clean cuts on downbeats (beat grid + transient detection)
- Instagram 9:16 / 3:4 crops with **face-follow** (macOS Vision), pans and per-shot reframing
- Hebrew/RTL lyric captions (CoreText-rendered PNG overlays) synced to the vocal with Demucs + Whisper

## Install

```bash
git clone git@github.com:electricmonk/music-video-edit.git ~/.claude/skills/music-video-edit
~/.claude/skills/music-video-edit/scripts/setup.sh   # venv, fonts, Swift tools → ~/.cache/music-video-edit
```
Requires ffmpeg (Homebrew), Python 3, and Xcode command-line tools with the license accepted.

See [SKILL.md](SKILL.md) for the workflow.
