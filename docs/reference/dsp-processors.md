# DSP Processors

This reference lists processors the AI creative director may request. Remixero validates production plans against this registry and only executes supported processors.

## Registry processors

| Processor | Role | Executable mode |
|-----------|------|-----------------|
| `granular` | Texture beds and rhythmic grain clouds | `granular` |
| `destroy` | Aggressive fragmentation and distortion | `destroy` |
| `collapse` | Progressive densification | `collapse` |
| `feedback` | Bounded feedback loop | `feedback` |
| `comb` | Metallic ringing / hollow tunnels | `comb` |
| `ring_mod` | Inharmonic ring-mod spectra | `ring_mod` |
| `pitch_warp` | Pitch and rate warping | `pitch_warp` |
| `stutter` | Glitch stutter slices | `stutter` |
| `pump` | Sidechain-style pump pressure | `pump` |
| `random` | Seeded fragmentation mix | `random` |
| `passthrough` | Near-dry reference bed | `smoke` |

## Parameter notes

- Every processor accepts **intensity** in `[0.0, 1.0]`.
- Feedback-oriented processors enforce hard upper bounds (for example feedback amount).
- AI plans may include automation events (`linear`, `step`, `exponential`) on parameters such as density, feedback, or volume.
- Unknown processors are removed during validation; Remixero does not invent SuperCollider for them.

:::hint{type="danger"}
Do not treat intensity as unlimited drive into open feedback. Remixero bounds feedback and applies limiting so intentional harshness does not become an unbounded loop.
:::

## Related articles

- [AI creative director](../concepts/ai-creative-director.md)
- [Remix modes](remix-modes.md)
- [Render with the AI creative director](../how-to/render-with-ai.md)
