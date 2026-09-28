# Render a Classic Remix

Use this procedure when you want a single remix mode to transform a source file without the AI creative director.

## Before you start

- Remixero is installed and on your `PATH`. See [Install and set up Remixero](install-and-setup.md).
- FFmpeg and SuperCollider are available.
- You have a source file in a supported format (`mp3`, `wav`, `flac`, or `ogg`).

## Render with explicit options

1. Open a terminal in the directory that contains your source file, or pass an absolute path.
2. Run Remixero with a mode, intensity, and seed:

```bash
remixero song.mp3 --mode destroy --intensity 0.9 --seed 42
```

3. Wait for analysis and render to finish.
4. Open the output directory (default: `output/`) and locate the new WAV and JSON metadata files.

## Prompt interactively

1. Run Remixero without **`--mode`** in an interactive terminal:

```bash
remixero song.mp3
```

2. When prompted, choose a mode from the interactive list.
3. When prompted, enter an intensity between `0.0` and `1.0`.
4. Review the written outputs in the output directory.

## Common options

1. Write results to another directory with **`--output`**.
2. Render several related results with **`--variations`**.
3. Cap analysis and render length with **`--duration`** or **`--preview`**.
4. Keep the SuperCollider patch beside the WAV with **`--keep-patch`**.
5. Write analysis JSON with **`--keep-analysis`**.

```bash
remixero song.mp3 \
  --mode granular \
  --intensity 0.6 \
  --seed 7 \
  --preview 15 \
  --output ./renders \
  --keep-patch \
  --keep-analysis
```

:::hint{type="success"}
Use **`--preview`** while exploring modes. It limits analysis and render to the first *N* seconds so iteration stays fast.
:::

## Related articles

- [Classic remix modes](../concepts/classic-modes.md)
- [Command-line options](../reference/cli-options.md)
- [Inspect plans, patches, and metadata](inspect-outputs.md)
