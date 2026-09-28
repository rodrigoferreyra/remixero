# Classic Remix Modes

Classic mode is Remixero’s non-AI path: you pick one remix strategy, set intensity and seed, and render. This page explains what classic modes are and how they relate to analysis and synthesis.

## How it works

1. Remixero analyzes the working copy of your source.
2. The selected **remix mode** maps intensity and a seeded random generator into structured **remix parameters**.
3. The SuperCollider generator turns those parameters into a patch and renders audio.

Interactive classic mode (TTY, no `--mode`) prompts for mode and intensity. Non-interactive runs default to *granular* at intensity `0.5` when those options are omitted.

## Key features

- **Single-strategy transforms** — one mode drives the whole render.
- **Intensity as transformation control** — intensity changes how aggressively the strategy mutates material; it is not a simple volume fader.
- **Seeded randomness** — procedural choices come from an explicit seed so you can reproduce a result.
- **Shared synthesis backend** — classic modes and AI layers use the same family of DSP primitives.

## Modes at a glance

| Mode | Character |
|------|-----------|
| `granular` | Overlapping grains; texture beds and rhythmic clouds |
| `destroy` | Aggressive fragmentation, distortion, and filtering |
| `collapse` | Progressive densification toward crushed texture |
| `feedback` | Bounded delay/feedback with filtering and limiting |
| `random` | Seeded mix of fragmentation primitives |
| `comb` | Comb-filter / resonator coloration |
| `ring_mod` | Ring modulation against a carrier |
| `pitch_warp` | Pitch and playback-rate warping |
| `stutter` | Rapid locked slices and freezes |
| `pump` | Sidechain-style pumping synced to tempo or transients |
| `smoke` | Near-dry reference path used for environment checks |

See [Remix modes](../reference/remix-modes.md) for the full reference list.

## Related articles

- [Render a classic remix](../how-to/render-a-classic-remix.md)
- [Intensity, seeds, and reproducibility](intensity-seeds-reproducibility.md)
- [DSP processors](../reference/dsp-processors.md)
