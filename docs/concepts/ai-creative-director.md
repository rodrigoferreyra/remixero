# AI Creative Director

The AI creative director turns a natural-language instruction into a structured **production plan**, then Remixero renders that plan with SuperCollider. This page explains what the AI path does and what it deliberately does not do.

## How it works

1. Remixero analyzes the source locally.
2. Optionally, with **`--hybrid-listen`**, a multimodal provider listens to the audio and returns a compact **listening brief**.
3. The configured **plan provider** returns a **production plan**: title, sections, layers, transitions, and global parameters.
4. Remixero validates and repairs the plan so every processor stays inside the executable DSP registry.
5. Timing alignment can snap sections to analysis-derived musical structure and attach crossfades.
6. The executor compiles layers into concurrent synthesis voices on a shared mix bus with limiting.
7. SuperCollider renders the output WAV.

Abstract briefs are valid. An instruction such as *make it hardcore edm* is expanded into sections, layers, and registry processors. Short or abstract briefs can also receive analysis-driven arrangement hints (build, drop, breakdown layout).

## Key features

- **Structured plans, not synthesis code** — the model outputs a production plan object; Remixero owns rendering.
- **Multi-layer mixing** — several processors can run as concurrent layers with volume, pan, automation, and section activity.
- **Registry-constrained processors** — unknown processors are dropped or repaired so the engine only runs supported DSP.
- **Provider choice** — plan generation can use more than one AI backend; provider selection is controlled by flags and environment variables.
- **Opt-in hybrid listen** — song-aware listening notes are available when you pass **`--hybrid-listen`** and a multimodal API key is configured.

## Main benefits

- Lets you describe creative intention without writing SuperCollider.
- Keeps plans inspectable with **`--keep-plan`** and **`--plan-only`**.
- Separates listening (optional), planning, and rendering so you can iterate on the first seconds with **`--preview`**.

:::hint{type="warning"}
AI providers design plans only. They do not write SuperCollider. If a plan requests unsupported processors, Remixero validates the plan before render and keeps only executable layers.
:::

## Hybrid listen

By default, text-only plan providers use **local analysis** only. Pass **`--hybrid-listen`** to request an audio listening pass first. Listening notes describe structure, salient moments, what to preserve, and what to destroy. Those notes are injected into the plan prompt.

If the listening pass fails or no multimodal key is available, Remixero continues with analysis-only planning.

When the plan provider already uploads audio for the full plan call, a separate listen pass is skipped to avoid duplicate cost.

## Related articles

- [Render with the AI creative director](../how-to/render-with-ai.md)
- [Use hybrid listen](../how-to/use-hybrid-listen.md)
- [DSP processors](../reference/dsp-processors.md)
