# Render With the AI Creative Director

Use this procedure to turn a natural-language instruction into a multi-layer remix. Remixero builds a production plan, validates it, and renders with SuperCollider.

## Before you start

- Remixero is installed with the AI extras (`pip install -e ".[ai]"`).
- At least one plan-provider API key is exported.
- You understand that the AI designs a **production plan**, not SuperCollider code. See [AI creative director](../concepts/ai-creative-director.md).

## Generate and render a plan

1. Export your plan-provider key.
2. Run Remixero with a prompt. **`--prompt`** implies AI mode:

```bash
export GROQ_API_KEY="your-key"
remixero song.mp3 \
  --provider groq \
  --prompt "make it hardcore edm" \
  --preview 15 \
  --yes \
  --keep-plan
```

3. Review the printed production plan summary.
4. If you did not pass **`--yes`**, confirm when asked before rendering.
5. Open the output directory for the WAV, metadata, and optional plan JSON.

## Generate a plan without rendering

1. Pass **`--plan-only`** (and usually **`--keep-plan`**):

```bash
remixero song.mp3 \
  --provider groq \
  --prompt "sparse then violent" \
  --plan-only \
  --keep-plan
```

2. Inspect the saved plan JSON before committing to a full render.

## Choose a provider

1. Pass **`--provider groq`** or **`--provider gemini`** to force a backend.
2. Omit **`--provider`** to let Remixero auto-select from available keys and configuration.

:::hint{type="info"}
Text-only plan providers use local analysis by default. They do not upload source audio unless you enable hybrid listen. Multimodal plan providers can upload audio as part of the plan request.
:::

## Override intensity after planning

1. Add **`--intensity`** when you want a fixed overall intensity regardless of the plan’s suggested value:

```bash
remixero song.mp3 \
  --provider groq \
  --prompt "industrial noise wall" \
  --intensity 0.85 \
  --yes
```

## Related articles

- [Use hybrid listen](use-hybrid-listen.md)
- [AI creative director](../concepts/ai-creative-director.md)
- [Command-line options](../reference/cli-options.md)
