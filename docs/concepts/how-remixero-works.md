# How Remixero Works

This page describes the Remixero processing pipeline from source audio to rendered output. Use it to understand where analysis, remix configuration, synthesis generation, and rendering fit together.

## How it works

Remixero keeps these stages separate:

1. **Input** — validate the source file and create a working WAV copy for analysis and render.
2. **Analysis** — measure duration, amplitude, spectral descriptors, estimated tempo, transients, and source segments. Analysis does not change the original file.
3. **Remix configuration** — choose classic mode parameters or an AI **production plan**.
4. **Remix strategy** — map intensity, seed, and analysis into structured transform parameters.
5. **Synthesis generation** — translate those parameters into a SuperCollider program.
6. **Rendering** — execute the program and write the output WAV.
7. **Output and metadata** — store reproducibility data next to the audio.

```text
Source audio
  → analysis
  → remix configuration (classic mode or AI plan)
  → remix strategy / plan execution
  → SuperCollider generation
  → rendering
  → WAV + metadata
```

## Classic path versus AI path

**Classic mode** selects one remix strategy (for example *destroy*) and maps **intensity** and **seed** into that strategy’s parameters.

**AI creative director** asks an AI provider for a **production plan**: sections, layers, processors, and transitions. Remixero validates the plan against an executable DSP registry, then compiles each layer into concurrent synthesis voices with a shared mix bus and limiter.

In both paths, SuperCollider owns audio synthesis. The AI provider never emits SuperCollider code.

## Source preservation and safety

- The original source file remains untouched.
- Existing output files are not overwritten silently; Remixero allocates the next free suffix.
- Feedback-oriented processors use bounded parameters and limiting to avoid runaway levels.

## Related articles

- [Classic remix modes](classic-modes.md)
- [AI creative director](ai-creative-director.md)
- [Intensity, seeds, and reproducibility](intensity-seeds-reproducibility.md)
- [Render a classic remix](../how-to/render-a-classic-remix.md)
