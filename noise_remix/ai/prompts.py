"""AI system / context prompts for production planning."""

from __future__ import annotations

import json
from typing import Any

from noise_remix.ai.registry import registry_for_prompt
from noise_remix.models.analysis import AudioAnalysis

SYSTEM_INSTRUCTION = """You are a creative producer for Remixero, an experimental/noise audio transformation system.

Your job is to design an evolving multi-layer production using ONLY the available processing primitives.
The engine WILL render every layer you specify as concurrent SuperCollider voices — this is not documentation.

Rules:
- Do not write executable code or SuperCollider.
- Do not invent processors or parameters outside the registry.
- Prefer 2–4 concurrent layers with complementary roles (bed, destroyer, color, accent).
- Use sections + active_layers to bring layers in and out over time.
- Put explicit numeric parameters in each layer's processing_chain when you care about them
  (feedback, delay_time, mod_freq, pitch_ratio, wet, drive, decay, etc.).
- Create contrast, development, and transitions — not one flat effect.
- Treat the source recording as raw material to transform.
- Follow the user's artistic instruction with specific, executable decisions.
- Return only the requested structured production plan JSON.
- Required top-level fields: title, description, duration_seconds, global_parameters, sections, layers.
- primary_mode must be a registered processor (used as metadata / fallback).
- every layer MUST have a stable string id and a registered processor.
- every sections[].active_layers entry MUST be an exact layers[].id (never invent names like "coloring").
- Feedback must remain bounded (never above the registry hard max).
- Prefer intentional structure over stacking every effect at once.
"""


def build_user_prompt(
    *,
    instruction: str,
    analysis: AudioAnalysis,
    duration_seconds: float,
    variation_index: int,
    variations: int,
) -> str:
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

    return f"""Creative instruction:
{instruction}

Target duration seconds: {duration_seconds}
{variation_note}

Local deterministic analysis (trust these numeric measurements):
{json.dumps(analysis_payload, indent=2)}

Available DSP capability registry (use ONLY these processors):
{json.dumps(capabilities, indent=2)}

Constraints:
- duration_seconds must be > 0 and <= {duration_seconds}
- global_parameters.primary_mode must be a registry processor
- every layer must include id + processor (registry processor only)
- sections is REQUIRED (non-empty array); each section needs start, end, name
- every active_layers entry must exactly match a layers[].id (no invented role names)
- include at least one section and at least two layers when the instruction asks for complexity
- set section.active_layers to control which layers play when
- use processing_chain parameters for concrete DSP values the renderer should honor
- design an evolving arrangement that the multi-layer SuperCollider mixer will actually render
"""


def analysis_context_dict(analysis: AudioAnalysis) -> dict[str, Any]:
    return {
        "duration": analysis.duration,
        "transient_count": len(analysis.transients),
        "segment_count": len(analysis.segments),
    }
