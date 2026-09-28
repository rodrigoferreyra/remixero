# What Is Remixero

Remixero is a local, command-line tool that transforms existing audio into experimental and noise-oriented remixes. This page explains what the product does, who it is for, and which principles shape its behavior.

## How it works

You provide a source audio file. Remixero analyzes that file, applies a remix strategy, generates a synthesis program for the SuperCollider engine, renders a new audio file, and writes metadata next to the result.

The product never modifies your original source file. Each run writes new files into an output directory and avoids overwriting existing renders by choosing a free numeric suffix.

## Key features

- **Classic remix modes** — apply one procedural transform such as granular, destroy, collapse, or feedback.
- **AI creative director** — describe an intention in natural language; Remixero builds a structured multi-layer **production plan**, then renders it with the same synthesis engine used by classic modes.
- **Deterministic seeds** — the same source, mode, parameters, and seed produce the same remix parameters.
- **Inspectable artifacts** — optional production-plan JSON, SuperCollider patch files, analysis JSON, and render metadata support debugging and iteration.
- **Local-first workflow** — analysis and rendering run on your machine; optional AI providers only design plans, never write synthesis code.

## Main benefits

- Treats the source as material to transform, not as a track that must stay musically intact.
- Keeps creative decisions in structured data, then renders through a controlled DSP path.
- Separates planning from rendering so you can inspect or discard a plan before committing CPU time to a full render.

:::hint{type="info"}
Remixero is experimental music software. Harsh distortion, dense texture, and aggressive processing are intentional. Uncontrolled feedback levels are not; feedback-oriented processors keep bounded parameters and limiting.
:::

## Related articles

- [How Remixero works](how-remixero-works.md)
- [Classic remix modes](classic-modes.md)
- [AI creative director](ai-creative-director.md)
