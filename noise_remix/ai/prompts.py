"""AI system / context prompts for production planning."""

from __future__ import annotations

import json
from typing import Any

from noise_remix.ai.registry import registry_for_prompt
from noise_remix.models.analysis import AudioAnalysis

SYSTEM_INSTRUCTION = """You are a creative producer for Remixero, an experimental/noise audio transformation system.

Your job: turn the user's artistic brief — including abstract genre/mood requests like
"make it hardcore EDM", "ambient doom", "glitchy IDM", or "destroy this pop song" —
into a concrete multi-layer production plan using ONLY the registry processors below.
The engine WILL render every layer as concurrent SuperCollider voices.

How to handle abstract instructions:
- Expand the vibe into structure yourself. Do NOT ask the user for processor names.
- Invent sections, layer roles, intensities, and processing_chain values that evoke the brief.
- Use analysis (transients, flux, centroid, segments) to place drops, builds, and breakdowns.
- Stay inside the registry. Approximate aesthetics with available tools; never invent processors.
- Aesthetic hints (non-exhaustive):
  hardcore / EDM / rave → pump + stutter + destroy pulses, high intensity, abrupt section cuts,
    pitch_warp risers, feedback/comb for pressure; low source_preservation in peak sections
  industrial / noise → destroy, collapse, feedback, ring_mod; dark filtering via params
  ambient / drone → pitch_warp + granular beds, slow section changes, higher source_preservation
  glitch / IDM → stutter + granular + occasional ring_mod; short contrasting sections
  metallic / bells → comb + ring_mod
  clear / radio edit → passthrough bed with sparse accents
  high / bright → pitch_warp upward; dark / heavy → feedback, comb, lower pitch_warp

Plan craft rules:
- Prefer 2–4 layers and 3–5 sections (rarely more than 6).
- Use sections + active_layers for arrangement (build / drop / breakdown / outro).
- Section changes are crossfaded by the engine; still prefer clear structural contrast.
- Put concrete numbers in processing_chain when it matters (feedback, delay_time, mod_freq,
  pitch_ratio, wet, drive, decay, etc.).
- Create contrast and development — not one static effect stack.
- Treat the source as raw material.
- Do not write executable code or SuperCollider.
- Return only the structured production plan JSON.
- Required: title, description, duration_seconds, global_parameters, sections, layers.
- primary_mode = a registry processor (metadata / fallback).
- every layer needs a stable string id + registry processor.
- every active_layers entry must be an exact layers[].id (no invented names like "coloring").
- Feedback must stay within registry hard max.
"""


def build_user_prompt(
    *,
    instruction: str,
    analysis: AudioAnalysis,
    duration_seconds: float,
    variation_index: int,
    variations: int,
    listening_brief: object | None = None,
) -> str:
    from noise_remix.ai.arrange import propose_section_bounds
    from noise_remix.ai.brief import classify_brief
    from noise_remix.ai.listen import ListeningBrief, listening_brief_as_prompt_block

    analysis_payload = {
        "duration": analysis.duration,
        "sample_rate": analysis.sample_rate,
        "channels": analysis.channels,
        "amplitude": analysis.amplitude.model_dump(),
        "dynamic_range_db": analysis.dynamic_range_db,
        "dynamic_range_label": analysis.dynamic_range_label,
        "spectral_flux": analysis.spectral_flux,
        "spectral_flux_label": analysis.spectral_flux_label,
        "spectral_centroid_hz": analysis.spectral_centroid_hz,
        "transient_count": len(analysis.transients),
        "segment_count": len(analysis.segments),
        "estimated_bpm": analysis.estimated_bpm,
        "segments_preview": [
            segment.model_dump() for segment in analysis.segments[:24]
        ],
    }
    capabilities = registry_for_prompt()
    variation_note = ""
    if variations > 1:
        variation_note = (
            f"\nThis is variation {variation_index + 1} of {variations}. "
            "Make it meaningfully different in structure, layering, and development — "
            "not just tiny numeric tweaks."
        )

    intent = classify_brief(instruction)
    suggested = propose_section_bounds(
        analysis, energy=str(intent.get("energy") or "medium")
    )
    arrangement_hint = (
        "\nSuggested analysis-based section layout (prefer these boundaries; "
        "fill processors/layers yourself):\n"
        + json.dumps(suggested, indent=2)
    )

    listening_block = ""
    if isinstance(listening_brief, ListeningBrief):
        listening_block = "\n" + listening_brief_as_prompt_block(listening_brief) + "\n"
    elif listening_brief is not None:
        # Allow pre-rendered string blocks in tests.
        listening_block = "\n" + str(listening_brief).strip() + "\n"

    return f"""Creative instruction (may be abstract — expand it into a full executable plan):
{instruction}

Target duration seconds: {duration_seconds}
{variation_note}
{arrangement_hint}
{listening_block}
Local deterministic analysis (use this to shape arrangement; estimated_bpm is approximate only):
{json.dumps(analysis_payload, indent=2)}

Available DSP capability registry (use ONLY these processors):
{json.dumps(capabilities, indent=2)}

Constraints:
- Interpret abstract briefs creatively; you choose sections/layers/parameters
- Prefer the suggested section boundaries above when the brief is abstract/genre-based
- When Gemini listening notes are present, align sections/layers to those song-specific moments
- duration_seconds must be > 0 and <= {duration_seconds}
- global_parameters.primary_mode must be a registry processor
- every layer must include id + processor (registry processor only)
- sections is REQUIRED (non-empty); each needs start, end, name, active_layers
- every active_layers entry must exactly match a layers[].id
- typically 3–5 sections and 2–4 layers unless the brief needs less
- use processing_chain for concrete DSP values the renderer should honor
- optional automation events (volume/feedback/pitch_ratio/density) are rendered over time
- design an evolving arrangement the multi-layer SuperCollider mixer will actually render
"""


def analysis_context_dict(analysis: AudioAnalysis) -> dict[str, Any]:
    return {
        "duration": analysis.duration,
        "transient_count": len(analysis.transients),
        "segment_count": len(analysis.segments),
    }
