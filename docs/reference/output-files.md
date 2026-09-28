# Output Files

This page describes the files Remixero writes after a run. Use it to locate audio, metadata, plans, patches, and analysis artifacts.

## Naming pattern

Remixero writes into the directory given by **`--output`** (default `output/`).

Base pattern:

```text
{source-stem}-{mode}-{nnn}.wav
{source-stem}-{mode}-{nnn}.json
```

Optional companions:

```text
{source-stem}-{mode}-{nnn}.scd      # with --keep-patch
{source-stem}-plan-{nnn}.json       # AI plan with --keep-plan / --plan-only
```

The numeric suffix increments until no conflicting file exists. Remixero does not overwrite existing outputs.

## File types

| Artifact | When written | Contents |
|----------|--------------|----------|
| `.wav` | Successful render | Rendered remix audio |
| `.json` (metadata) | Successful render | Source hash, seed, intensity, mode, parameter summaries, analysis summary |
| `.scd` | `--keep-patch` | Exact SuperCollider program used for that render |
| plan `.json` | `--keep-plan` or `--plan-only` | Validated AI production plan |
| analysis `.json` | `--keep-analysis` | Structured local analysis results |

## Metadata fields

Render metadata includes:

- `source` — source file name
- `source_hash` — hash of the original source for reproducibility
- `mode` — remix mode or AI-derived primary mode
- `intensity` — intensity used for the render
- `seed` — seed used for procedural choices
- `duration` — render duration in seconds
- `created_at` — UTC timestamp
- `software_version` — Remixero version
- `supercollider_version` — synthesis engine version when detected
- `parameters` — compact parameter details (large grain/event lists summarized by count)
- `analysis_summary` — duration, sample rate, channels, transient/segment counts, spectral labels, estimated BPM

AI renders may embed a compact `ai_plan` object inside `parameters`.

## Related articles

- [Inspect plans, patches, and metadata](../how-to/inspect-outputs.md)
- [Intensity, seeds, and reproducibility](../concepts/intensity-seeds-reproducibility.md)
- [How Remixero works](../concepts/how-remixero-works.md)
