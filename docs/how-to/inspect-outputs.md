# Inspect Plans, Patches, and Metadata

This page shows how to keep and review Remixero artifacts after a run. Use it when you need to debug a render, compare variations, or understand what the AI planned.

## Keep a production plan

1. Add **`--keep-plan`** to an AI run, or use **`--plan-only`**.
2. Open the plan JSON written under the output directory.
3. Check sections, layers, processors, and transitions against what you intended.

```bash
remixero song.mp3 \
  --provider groq \
  --prompt "feedback wall after a sparse intro" \
  --plan-only \
  --keep-plan
```

## Keep the SuperCollider patch

1. Add **`--keep-patch`** to classic or AI runs.
2. Open the `.scd` file next to the WAV.
3. Confirm the patch matches the parameters or plan you expected.

:::hint{type="info"}
When **`--keep-patch`** is enabled, Remixero preserves the exact patch used for that render. Metadata generation does not regenerate a different patch.
:::

## Keep analysis JSON

1. Add **`--keep-analysis`**.
2. Open the analysis JSON to review duration, segments, transients, spectral labels, and estimated BPM.

## Read render metadata

1. Locate the `.json` file that shares the WAV stem (`source-mode-001.json`).
2. Verify `source_hash`, `seed`, `intensity`, `mode`, and parameter summaries.
3. For AI renders, look for the compact `ai_plan` summary inside `parameters` when present.

## Related articles

- [Output files](../reference/output-files.md)
- [Intensity, seeds, and reproducibility](../concepts/intensity-seeds-reproducibility.md)
- [How Remixero works](../concepts/how-remixero-works.md)
