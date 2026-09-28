# Install and Set Up Remixero

This page walks through installing Remixero and preparing the tools it needs to analyze and render audio. Complete these steps before you run classic or AI remixes.

## Requirements

- Python 3.11 or newer
- FFmpeg (`ffmpeg` and `ffprobe` on your `PATH`)
- SuperCollider (`sclang` and `scsynth` on your `PATH`)
- Optional AI extras: provider API keys when you use the creative director

## Install Remixero

1. Open a terminal in the Remixero project directory.
2. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install the package with development and AI optional dependencies:

```bash
pip install -e ".[dev,ai]"
```

4. Confirm the CLI is available:

```bash
remixero --help
```

:::hint{type="info"}
An editable install (`pip install -e`) picks up local code changes without a reinstall.
:::

## Configure AI providers (optional)

1. Export the API key for the plan provider you intend to use.
2. Optionally set the provider and model overrides.

```bash
export GROQ_API_KEY="your-key"
# optional:
export REMIXERO_AI_PROVIDER=groq
export REMIXERO_GROQ_MODEL=openai/gpt-oss-20b
```

For multimodal plan or hybrid listen workflows, also export a Gemini-compatible key:

```bash
export GEMINI_API_KEY="your-key"
# or
export GOOGLE_API_KEY="your-key"
```

:::hint{type="warning"}
Do not store API keys in `remixero.toml`. Keys belong in environment variables only.
:::

## Optional project configuration

Copy `remixero.toml.example` to `remixero.toml` in the project directory if you want local defaults for provider and models. See [Configuration and environment variables](../reference/configuration.md).

## Verify external tools

1. Confirm FFmpeg responds:

```bash
ffmpeg -version
ffprobe -version
```

2. Confirm SuperCollider responds:

```bash
sclang -v
```

3. Run the test suite when you want a local health check:

```bash
pytest
```

## Related articles

- [Render a classic remix](render-a-classic-remix.md)
- [Render with the AI creative director](render-with-ai.md)
- [Configuration and environment variables](../reference/configuration.md)
