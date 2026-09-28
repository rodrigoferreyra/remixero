# Configuration and Environment Variables

This page lists Remixero configuration sources for AI behavior and models. API keys must live in the environment, never in project config files.

## Configuration sources

Remixero reads AI settings from:

1. CLI flags such as **`--provider`**
2. Environment variables
3. Optional `remixero.toml` in the working directory

Later sources do not override an explicit CLI provider override. Environment model overrides take precedence over TOML values for the matching keys.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | API key for Groq plan generation |
| `GEMINI_API_KEY` | API key for Gemini plan generation and hybrid listen |
| `GOOGLE_API_KEY` | Alternate Gemini/Google key (used if `GEMINI_API_KEY` is unset) |
| `REMIXERO_AI_PROVIDER` | Default provider: `groq` or `gemini` |
| `REMIXERO_GROQ_MODEL` | Groq model id |
| `REMIXERO_GEMINI_MODEL` | Gemini model id (plan and listen) |
| `REMIXERO_AI_MAX_RETRIES` | Shared retry count |
| `REMIXERO_AI_RETRY_BASE` | Base retry delay in seconds |
| `REMIXERO_AI_RETRY_MAX` | Maximum retry delay in seconds |
| `REMIXERO_GEMINI_MAX_RETRIES` | Gemini-specific retry override |
| `REMIXERO_GEMINI_RETRY_BASE` | Gemini-specific base delay override |
| `REMIXERO_GEMINI_RETRY_MAX` | Gemini-specific max delay override |

## Example `remixero.toml`

```toml
[ai]
enabled = false
provider = "groq"
gemini_model = "gemini-3.8-flash"
groq_model = "openai/gpt-oss-20b"
max_retries = 5
retry_base_seconds = 2.0
retry_max_seconds = 45.0
```

See `remixero.toml.example` in the repository root.

:::hint{type="warning"}
Hybrid listen is controlled by the **`--hybrid-listen`** CLI flag, not by TOML alone.
:::

## Related articles

- [Install and set up Remixero](../how-to/install-and-setup.md)
- [Use hybrid listen](../how-to/use-hybrid-listen.md)
- [Command-line options](cli-options.md)
