# Remixero

CLI-first procedural noise remix tool. Transforms audio with SuperCollider into experimental/noise variations.

Optional AI creative-director mode (Gemini or Groq) designs a structured production plan; SuperCollider still renders audio.

## Requirements

- Python 3.11+
- FFmpeg (`ffmpeg`, `ffprobe`)
- SuperCollider (`sclang`, `scsynth`)
- Optional AI: `pip install -e ".[ai]"` plus `GEMINI_API_KEY` and/or `GROQ_API_KEY`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ai]"
export GROQ_API_KEY="..."          # or GEMINI_API_KEY
```

## Classic modes

```bash
remixero song.mp3 --mode destroy --intensity 0.9 --seed 42
```

## AI creative director

The AI designs a structured multi-layer production plan (not SuperCollider code).
Remixero compiles every layer into concurrent SuperCollider voices (grains, fragments,
feedback, comb, ring-mod, pitch-warp, stutter, passthrough) with a shared mix bus and limiter.

Abstract briefs are fine — e.g. `--prompt "make it hardcore edm"`. The model expands genre/mood
into sections, layers, and registry processors. More specific briefs still give tighter control.

```bash
# Abstract
remixero song.mp3 --provider groq --prompt "make it hardcore edm" --yes --keep-plan

# Groq (good when Gemini is overloaded)
remixero song.mp3 --provider groq --prompt "industrial noise then feedback wall" --yes --keep-plan

# Gemini
remixero song.mp3 --provider gemini --prompt "sparse then violent" --yes

# Auto: if only GROQ_API_KEY is set, Groq is selected
remixero song.mp3 --prompt "destroy this" --plan-only --keep-plan
```

Override models:

```bash
export REMIXERO_AI_PROVIDER=groq
export REMIXERO_GROQ_MODEL=openai/gpt-oss-20b
export REMIXERO_GEMINI_MODEL=gemini-3.8-flash
```

Groq uses local analysis only (no source-audio upload). Gemini can upload audio via the Files API when available.

Use `--keep-patch` to inspect the generated `.scd` and confirm multiple SynthDefs / layers.

## Tests

```bash
pytest
```
