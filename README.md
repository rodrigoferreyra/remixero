# Remixero

Remixero is a local, command-line tool that transforms existing audio into experimental and noise-oriented remixes. You provide a source file; Remixero analyzes it, applies a remix strategy, generates a SuperCollider program, renders a new audio file, and writes metadata next to the result.

The product never modifies your original source file. Each run writes new files into an output directory and avoids overwriting existing renders by choosing a free numeric suffix.

Harsh distortion, dense texture, and aggressive processing are intentional. Uncontrolled feedback levels are not; feedback-oriented processors keep bounded parameters and limiting.

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

**Classic mode** selects one remix strategy (for example *destroy*) and maps **intensity** and **seed** into that strategy’s parameters.

**AI creative director** asks an AI provider for a **production plan**: sections, layers, processors, and transitions. Remixero validates the plan against an executable DSP registry, then compiles each layer into concurrent synthesis voices with a shared mix bus and limiter.

In both paths, SuperCollider owns audio synthesis. The AI provider never emits SuperCollider code.

## Key features

- **Classic remix modes** — apply one procedural transform such as granular, destroy, collapse, or feedback.
- **AI creative director** — describe an intention in natural language; Remixero builds a structured multi-layer production plan, then renders it with the same synthesis engine used by classic modes.
- **Deterministic seeds** — the same source, mode, parameters, and seed produce the same remix parameters.
- **Inspectable artifacts** — optional production-plan JSON, SuperCollider patch files, analysis JSON, and render metadata support debugging and iteration.
- **Local-first workflow** — analysis and rendering run on your machine; optional AI providers only design plans, never write synthesis code.

## Classic remix modes

Classic mode is the non-AI path: you pick one remix strategy, set intensity and seed, and render.

1. Remixero analyzes the working copy of your source.
2. The selected **remix mode** maps intensity and a seeded random generator into structured remix parameters.
3. The SuperCollider generator turns those parameters into a patch and renders audio.

Interactive classic mode (TTY, no `--mode`) prompts for mode and intensity. Non-interactive runs default to *granular* at intensity `0.5` when those options are omitted.

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

## AI creative director

The AI creative director turns a natural-language instruction into a structured **production plan**, then Remixero renders that plan with SuperCollider.

1. Remixero analyzes the source locally.
2. Optionally, with **`--hybrid-listen`**, a multimodal provider listens to the audio and returns a compact **listening brief**.
3. The configured **plan provider** returns a production plan: title, sections, layers, transitions, and global parameters.
4. Remixero validates and repairs the plan so every processor stays inside the executable DSP registry.
5. Timing alignment can snap sections to analysis-derived musical structure and attach crossfades.
6. The executor compiles layers into concurrent synthesis voices on a shared mix bus with limiting.
7. SuperCollider renders the output WAV.

Abstract briefs such as *make it hardcore edm* are accepted and expanded into sections and layers, but they often produce generic plans. Without audio listen, the plan provider only sees local analysis (duration, segments, transients, spectral labels) — not labeled choruses, vocals, or hooks. Stronger analysis-only prompts describe **energy arcs**, **section contrast**, **processor families**, and **source preservation**, optionally with **times in seconds**. Song-specific language (chorus, vocal hook) becomes useful when **`--hybrid-listen`** or a multimodal plan provider has actually heard the source.

AI providers design plans only. They do not write SuperCollider. If a plan requests unsupported processors, Remixero validates the plan before render and keeps only executable layers.

### Hybrid listen

By default, text-only plan providers use **local analysis** only. Pass **`--hybrid-listen`** to request an audio listening pass first. Listening notes describe structure, salient moments, what to preserve, and what to destroy. Those notes are injected into the plan prompt.

If the listening pass fails or no multimodal key is available, Remixero continues with analysis-only planning. Having both API keys set does not enable listening by itself; **`--hybrid-listen`** is required.

When the plan provider already uploads audio for the full plan call (`--provider gemini`), a separate listen pass is skipped to avoid duplicate cost.

## Intensity, seeds, and reproducibility

**Intensity** is a transformation parameter in the range `0.0`–`1.0`. Each remix strategy maps intensity onto its own DSP controls. Intensity is not implemented as a final volume multiply.

All procedural randomness uses an explicit **seed**.

- Pass an integer with **`--seed`** to lock the result.
- Pass *random* (the default) to draw a new seed for the run.
- With **`--variations`**, each variation derives a distinct seed from the base seed.

The same source file, mode or plan configuration, parameters, and seed produce the same generated remix configuration. Floating-point audio samples are not guaranteed bit-identical across machines or SuperCollider versions.

Estimated BPM and other heuristic analysis fields are approximate. Treat them as arrangement hints, not authoritative tempo truth.

Every successful render writes a JSON metadata file beside the WAV with source hash, seed, intensity, mode, parameter summaries, and analysis summaries.

---

## Requirements

- Python 3.11 or newer
- FFmpeg (`ffmpeg` and `ffprobe` on your `PATH`)
- SuperCollider (`sclang` and `scsynth` on your `PATH`)
- Optional AI extras: provider API keys when you use the creative director

## Install Remixero

1. Open a terminal in the Remixero project directory.
2. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install the package with development and AI optional dependencies:

```bash
pip install -e ".[dev,ai]"
```

4. Confirm the CLI is available:

```bash
remixero --help
```

An editable install (`pip install -e`) picks up local code changes without a reinstall.

### Configure AI providers (optional)

1. Export the API key for the plan provider you intend to use.
2. Optionally set the provider and model overrides.

```bash
export GROQ_API_KEY="your-key"
# optional:
export REMIXERO_AI_PROVIDER=groq
export REMIXERO_GROQ_MODEL=openai/gpt-oss-20b
```

For multimodal plan or hybrid listen workflows, also export a Gemini-compatible key:

```bash
export GEMINI_API_KEY="your-key"
# or
export GOOGLE_API_KEY="your-key"
```

Do not store API keys in `remixero.toml`. Keys belong in environment variables only.

Copy `remixero.toml.example` to `remixero.toml` if you want local defaults for provider and models.

### Verify external tools

1. Confirm FFmpeg responds:

```bash
ffmpeg -version
ffprobe -version
```

2. Confirm SuperCollider responds:

```bash
sclang -v
```

3. Run the test suite when you want a local health check:

```bash
pytest
```

## Render a classic remix

1. Open a terminal and pass a source file with a mode, intensity, and seed:

```bash
remixero song.mp3 --mode destroy --intensity 0.9 --seed 42
```

2. Wait for analysis and render to finish.
3. Open the output directory (default: `output/`) and locate the new WAV and JSON metadata files.

To prompt interactively, run without **`--mode`** in a TTY:

```bash
remixero song.mp3
```

Common options:

```bash
remixero song.mp3 \
  --mode granular \
  --intensity 0.6 \
  --seed 7 \
  --preview 15 \
  --output ./renders \
  --keep-patch \
  --keep-analysis
```

Use **`--preview`** while exploring modes. It limits analysis and render to the first *N* seconds so iteration stays fast.

## Render with the AI creative director

1. Export your plan-provider key.
2. Run Remixero with a prompt that specifies transform behavior, not only a genre label. **`--prompt`** implies AI mode:

```bash
export GROQ_API_KEY="your-key"
remixero song.mp3 \
  --provider groq \
  --prompt "Sparse low-intensity open, mid section builds with stutter and pitch_warp, final third full destroy+pump+feedback wall; overall source preservation low after the midpoint" \
  --preview 20 \
  --yes \
  --keep-plan
```

3. Review the printed production plan summary. Check that sections, layers, and processors match the intention before you keep iterating.
4. If you did not pass **`--yes`**, confirm when asked before rendering.
5. Open the output directory for the WAV, metadata, and optional plan JSON.

### Write stronger prompts

By default (Groq without **`--hybrid-listen`**), the planner does **not** hear the track. It only receives local analysis and your text. Asking it to target “the chorus” or “keep the vocal hook” without a listening pass does not give it those landmarks.

**Without listen**, prefer prompts that use what analysis can support:

1. **Energy arc and contrast** — sparse → dense, quiet bed → crush, long build then abrupt cut.
2. **Relative placement** — early / middle / late, or approximate times in seconds if you know them.
3. **Processor families** — *pump*, *stutter*, *feedback*, *destroy*, *pitch_warp*, *comb*, *ring_mod*.
4. **Source preservation** — how recognizable the source should stay in peak sections (`high` / `low`, or a numeric intent the model can map).
5. **Layer roles** — bed vs pulse vs pressure, not song form labels the model cannot verify.

Examples that work without audio listen:

```bash
# Energy arc + processors + preservation
--prompt "Sparse granular bed for the first third, then stutter pulses, then destroy+pump+feedback at high intensity; low source preservation in the last third"

# Time-based if you already know the map
--prompt "0–8s almost dry/passthrough accents only; 8–20s comb+ring_mod metallic tension; after 20s full collapse with feedback under 0.8"

# Genre as seasoning, not the whole brief
--prompt "Hardcore pressure: pump and stutter throughout, pitch_warp risers into each section change, destroy on peaks; avoid a static single-effect stack"
```

**With listen** (`--hybrid-listen`, or `--provider gemini` with audio upload), the planner can use song-aware notes. Then musical landmarks make sense:

```bash
--prompt "Make the chorus hit hardcore — keep the vocal hook readable, crush pads into distortion, sidechain-pump the bed, stutter on the drop"
```

Weaker starting point (accepted, but often generic either way):

```bash
--prompt "make it hardcore edm"
```

### Iterate quickly

1. Use **`--preview 15`** or **`--preview 20`** while shaping the brief.
2. Use **`--keep-plan`** and read the plan JSON when the render misses the mark.
3. Raise force with **`--intensity 0.85`**–`0.95` if the plan looks timid after validation.
4. Add **`--hybrid-listen`** only when you need real song moments (chorus, vocal entry) and a multimodal key is available.

To generate a plan without rendering:

```bash
remixero song.mp3 \
  --provider groq \
  --prompt "Sparse open, then violent feedback wall; low source preservation after the midpoint" \
  --plan-only \
  --keep-plan
```

Pass **`--provider groq`** or **`--provider gemini`** to force a backend, or omit **`--provider`** to auto-select from available keys.

## Use hybrid listen

Hybrid listen asks a multimodal provider to listen to the source audio before a text-oriented plan provider builds the production plan. It is **off by default**.

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
4. Wait for the listening pass, then the plan request.

If listen cannot run (missing key or upload failure), Remixero continues with local analysis only.

## Inspect plans, patches, and metadata

Keep a production plan with **`--keep-plan`** or **`--plan-only`**, then open the plan JSON under the output directory.

Keep the SuperCollider patch with **`--keep-patch`**. Remixero preserves the exact `.scd` used for that render.

Keep analysis JSON with **`--keep-analysis`**.

Render metadata lives in the `.json` file that shares the WAV stem. Check `source_hash`, `seed`, `intensity`, `mode`, and parameter summaries. AI runs may include a compact `ai_plan` summary inside `parameters`.

---

## Reference

### Command-line options

```bash
remixero [OPTIONS] INPUT
```

`INPUT` is a required path to source audio (`mp3`, `wav`, `flac`, or `ogg`).

| Option | Short | Description |
|--------|-------|-------------|
| `--mode` | `-m` | Remix mode. If omitted in a TTY (non-AI), prompts interactively. |
| `--intensity` | `-i` | Transformation intensity in `[0.0, 1.0]`. Default `0.5` (or prompted in TTY). |
| `--variations` |  | Number of variations to render. Default `1`. |
| `--seed` |  | Integer seed or `random`. Default `random`. |
| `--output` | `-o` | Output directory. Default `output`. |
| `--duration` |  | Max source/render duration in seconds. |
| `--preview` |  | Analyze and render only the first *N* seconds. |
| `--keep-patch` |  | Retain the generated SuperCollider `.scd` next to the WAV. |
| `--keep-analysis` |  | Write analysis JSON next to outputs. |
| `--ai` |  | Enable AI creative-director mode. |
| `--provider` |  | AI provider: `gemini` or `groq` (default: auto). |
| `--prompt` / `--instruction` |  | Natural-language creative instruction (implies AI mode). |
| `--yes` | `-y` | Skip render confirmation in AI mode. |
| `--keep-plan` |  | Write the validated AI production plan JSON. |
| `--hybrid-listen` |  | With Groq planning: run a Gemini listen pass first (requires a Gemini key). |
| `--plan-only` |  | Generate and print a plan without rendering. |
| `--verbose` | `-v` | Show additional diagnostic detail. |
| `--version` |  | Show version and exit. |
| `--help` |  | Show help and exit. |

`--prompt`, `--plan-only`, or `--ai` enter AI mode. When both `--preview` and `--duration` are set, Remixero uses the smaller effective duration.

### Remix modes

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

Interactive TTY prompts offer `granular`, `destroy`, `collapse`, `feedback`, and `random`. All registered modes remain available through **`--mode`**.

### DSP processors

AI production plans may only request processors from this registry. Unknown processors are removed during validation.

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

Every processor accepts **intensity** in `[0.0, 1.0]`. Feedback-oriented processors enforce hard upper bounds. Plans may include automation events (`linear`, `step`, `exponential`) on parameters such as density, feedback, or volume.

### Configuration and environment variables

Remixero reads AI settings from:

1. CLI flags such as **`--provider`**
2. Environment variables
3. Optional `remixero.toml` in the working directory

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

Example `remixero.toml`:

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

See `remixero.toml.example` in the repository root. Hybrid listen is controlled by **`--hybrid-listen`**, not by TOML alone.

### Output files

Remixero writes into the directory given by **`--output`** (default `output/`).

```text
{source-stem}-{mode}-{nnn}.wav
{source-stem}-{mode}-{nnn}.json
{source-stem}-{mode}-{nnn}.scd      # with --keep-patch
{source-stem}-plan-{nnn}.json       # AI plan with --keep-plan / --plan-only
```

The numeric suffix increments until no conflicting file exists. Remixero does not overwrite existing outputs.

| Artifact | When written | Contents |
|----------|--------------|----------|
| `.wav` | Successful render | Rendered remix audio |
| `.json` (metadata) | Successful render | Source hash, seed, intensity, mode, parameter summaries, analysis summary |
| `.scd` | `--keep-patch` | Exact SuperCollider program used for that render |
| plan `.json` | `--keep-plan` or `--plan-only` | Validated AI production plan |
| analysis `.json` | `--keep-analysis` | Structured local analysis results |

Metadata fields include `source`, `source_hash`, `mode`, `intensity`, `seed`, `duration`, `created_at`, `software_version`, `supercollider_version`, `parameters`, and `analysis_summary`.

## Tests

```bash
pytest
```
