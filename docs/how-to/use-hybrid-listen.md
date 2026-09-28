# Use Hybrid Listen

Hybrid listen is an opt-in step that asks a multimodal provider to listen to the source audio before a text-oriented plan provider builds the production plan. Use this page when you want song-specific listening notes without switching the whole plan call to a multimodal provider.

## Before you start

- A plan-provider key is available (typically for Groq).
- A multimodal listen key is exported (`GEMINI_API_KEY` or `GOOGLE_API_KEY`).
- You understand hybrid listen is **off by default**.

## Run hybrid listen with Groq planning

1. Export both keys.
2. Pass **`--provider groq`** and **`--hybrid-listen`**:

```bash
export GROQ_API_KEY="your-key"
export GEMINI_API_KEY="your-key"

remixero song.mp3 \
  --provider groq \
  --hybrid-listen \
  --prompt "make this chorus hardcore — keep the vocal hook readable" \
  --preview 20 \
  --yes \
  --keep-plan
```

3. Confirm the CLI reports that hybrid listen is on.
4. Wait for the listening pass status lines, then the plan request.
5. Review the plan and rendered output as usual.

## What happens when listen cannot run

1. If you pass **`--hybrid-listen`** without a multimodal key, Remixero continues with local analysis only and reports that listen was skipped.
2. If upload or listening fails, Remixero does not abort the run. Planning continues with analysis-only context.

## When not to use hybrid listen

- You only have a text plan-provider key.
- The plan provider already uploads audio for the full plan (`--provider gemini`). A separate listen pass is skipped there.
- You want the lowest latency or cost and local analysis is enough.

:::hint{type="warning"}
Hybrid listen requires an explicit **`--hybrid-listen`** flag. Having both API keys set does not enable listening by itself.
:::

## Related articles

- [AI creative director](../concepts/ai-creative-director.md)
- [Render with the AI creative director](render-with-ai.md)
- [Configuration and environment variables](../reference/configuration.md)
