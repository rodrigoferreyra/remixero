# Remixero

CLI-first procedural noise remix tool. Transforms audio with SuperCollider into experimental and noise-oriented variations.

Optional AI creative-director mode designs a structured production plan; SuperCollider still renders audio.

## Documentation

Start with the knowledge base:

- **[Documentation home](docs/README.md)** — informative, instructional, and reference articles
- [What is Remixero](docs/concepts/what-is-remixero.md)
- [Install and set up](docs/how-to/install-and-setup.md)
- [Render a classic remix](docs/how-to/render-a-classic-remix.md)
- [Render with AI](docs/how-to/render-with-ai.md)
- [Command-line options](docs/reference/cli-options.md)

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ai]"

# Classic mode
remixero song.mp3 --mode destroy --intensity 0.9 --seed 42

# AI creative director (analysis-only planning by default)
export GROQ_API_KEY="..."
remixero song.mp3 --provider groq --prompt "make it hardcore edm" --preview 15 --yes --keep-plan
```

## Requirements

- Python 3.11+
- FFmpeg (`ffmpeg`, `ffprobe`)
- SuperCollider (`sclang`, `scsynth`)
- Optional AI: `pip install -e ".[ai]"` plus provider API keys

## Tests

```bash
pytest
```
