# Command-Line Options

This page lists Remixero CLI options for quick lookup. For conceptual background, see [How Remixero works](../concepts/how-remixero-works.md). For step-by-step usage, see the [how-to guides](../README.md).

## Synopsis

```bash
remixero [OPTIONS] INPUT
```

`INPUT` is a required path to source audio (`mp3`, `wav`, `flac`, or `ogg`).

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--mode` | `-m` | Remix mode. If omitted in a TTY (non-AI), prompts interactively. |
| `--intensity` | `-i` | Transformation intensity in `[0.0, 1.0]`. Default `0.5` (or prompted in TTY). |
| `--variations` |  | Number of variations to render. Default `1`. |
| `--seed` |  | Integer seed or `random`. Default `random`. |
| `--output` | `-o` | Output directory. Default `output`. |
| `--duration` |  | Max source/render duration in seconds. |
| `--preview` |  | Analyze and render only the first *N* seconds. |
| `--keep-patch` |  | Retain the generated SuperCollider `.scd` next to the WAV. |
| `--keep-analysis` |  | Write analysis JSON next to outputs. |
| `--ai` |  | Enable AI creative-director mode. |
| `--provider` |  | AI provider: `gemini` or `groq` (default: auto). |
| `--prompt` / `--instruction` |  | Natural-language creative instruction (implies AI mode). |
| `--yes` | `-y` | Skip render confirmation in AI mode. |
| `--keep-plan` |  | Write the validated AI production plan JSON. |
| `--hybrid-listen` |  | With Groq planning: run a Gemini listen pass first (requires a Gemini key). |
| `--plan-only` |  | Generate and print a plan without rendering. |
| `--verbose` | `-v` | Show additional diagnostic detail. |
| `--version` |  | Show version and exit. |
| `--help` |  | Show help and exit. |

## Notes

- **`--prompt`**, **`--plan-only`**, or **`--ai`** enter AI mode.
- **`--preview`** and **`--duration`** both limit length; when both are set, Remixero uses the smaller effective duration.
- **`--hybrid-listen`** is opt-in and does nothing useful without a multimodal API key when planning with Groq.

## Related articles

- [Remix modes](remix-modes.md)
- [Configuration and environment variables](configuration.md)
- [Render a classic remix](../how-to/render-a-classic-remix.md)
