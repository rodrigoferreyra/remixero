# Intensity, Seeds, and Reproducibility

This page explains how Remixero controls transformation strength and how you reproduce a result. Use it when you need predictable experiments or comparable variations.

## Intensity

**Intensity** is a transformation parameter in the range `0.0`–`1.0`. Each remix strategy maps intensity onto its own DSP controls (grain density, distortion, feedback amount, pump depth, and similar values).

Intensity is not implemented as a final volume multiply. Raising intensity changes how the material is processed, not only how loud the file is.

In AI mode, you can still pass **`--intensity`** to override the plan’s overall intensity after the plan is received.

## Seeds

All procedural randomness uses an explicit **seed**.

- Pass an integer with **`--seed`** to lock the result.
- Pass *random* (the default) to draw a new seed for the run.
- With **`--variations`**, each variation derives a distinct seed from the base seed.

The same source file, mode or plan configuration, parameters, and seed produce the same generated remix configuration. Floating-point audio samples are not guaranteed bit-identical across machines or SuperCollider versions.

## Reproducibility metadata

Every successful render writes a JSON metadata file beside the WAV. Metadata records source path, source hash, mode, intensity, seed, duration, software version, synthesis engine version when available, parameter summaries, and analysis summaries. AI runs can include a compact plan summary inside the parameters object.

:::hint{type="info"}
Estimated BPM and other heuristic analysis fields are approximate. Treat them as arrangement hints, not authoritative tempo truth.
:::

## Related articles

- [How Remixero works](how-remixero-works.md)
- [Output files](../reference/output-files.md)
- [Inspect plans, patches, and metadata](../how-to/inspect-outputs.md)
