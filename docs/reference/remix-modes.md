# Remix Modes

This reference lists classic remix modes registered in Remixero. For an overview of the classic path, see [Classic remix modes](../concepts/classic-modes.md).

## Mode table

| Mode | Description |
|------|-------------|
| `granular` | Fragment source audio into overlapping grains with rate, pan, and reverse variation. |
| `destroy` | Aggressive fragmentation with extreme rates, distortion, and filtering. |
| `collapse` | Progressive densification and degradation toward crushed texture. |
| `feedback` | Bounded delay/feedback loop with filtering, soft clipping, pitch smear, and hard limiting. |
| `comb` | Comb-filter / resonator coloration over looping source playback. |
| `ring_mod` | Ring modulation against a carrier for harsh, inharmonic spectra. |
| `pitch_warp` | Continuous pitch shifting and playback-rate warping with dispersion. |
| `stutter` | Rapid locked buffer slices and freezes with occasional jumps. |
| `pump` | Sidechain-style pumping synced to tempo or transients, with transient boost. |
| `random` | Seeded combination of fragmentation primitives. |
| `smoke` | Near-dry source with limiter; used as a reference / environment check path. |

## Interactive subset

When Remixero prompts for a mode in a TTY, the interactive list includes:

- `granular`
- `destroy`
- `collapse`
- `feedback`
- `random`

All registered modes remain available through **`--mode`**.

## Related articles

- [DSP processors](dsp-processors.md)
- [Command-line options](cli-options.md)
- [Render a classic remix](../how-to/render-a-classic-remix.md)
