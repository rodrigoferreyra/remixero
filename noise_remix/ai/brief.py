"""Interpret abstract creative briefs and bias production plans."""

from __future__ import annotations

import re

from noise_remix.models.production import AudioLayer, ProductionPlan, ProductionSection

_HIGH_ENERGY = re.compile(
    r"\b("
    r"hardcore|edm|rave|techno|trance|dubstep|drum\s*and\s*bass|dnb|d&b|"
    r"industrial|harsh|brutal|violent|aggressive|destroy|crush|chaos|"
    r"club|festival|drop|banger|hyper|maximal"
    r")\b",
    re.IGNORECASE,
)
_LOW_ENERGY = re.compile(
    r"\b("
    r"ambient|drone|soft|gentle|calm|sparse|minimal|quiet|delicate|"
    r"lofi|lo-fi|chill|meditat|dreamy|washed"
    r")\b",
    re.IGNORECASE,
)
_GLITCH = re.compile(
    r"\b(glitch|idm|stutter|breakcore|chop|slice|garble)\b",
    re.IGNORECASE,
)
_METALLIC = re.compile(
    r"\b(metal+ic|bells?|clang|resonant|ring\s*mod)\b",
    re.IGNORECASE,
)


def classify_brief(instruction: str) -> dict[str, str | bool]:
    """Return coarse intent flags derived from a natural-language brief."""
    text = instruction or ""
    high = bool(_HIGH_ENERGY.search(text))
    low = bool(_LOW_ENERGY.search(text)) and not high
    return {
        "energy": "high" if high else ("low" if low else "medium"),
        "glitch": bool(_GLITCH.search(text)),
        "metallic": bool(_METALLIC.search(text)),
        "abstract": len(text.split()) <= 12 or high or low,
    }


def apply_brief_intent(plan: ProductionPlan, instruction: str) -> ProductionPlan:
    """Bias a plan so abstract high/low-energy briefs are audible in the render.

    The LLM sometimes returns timid plans for vibe-only prompts. This post-pass
    raises intensity / adds complementary layers without inventing new processors.
    """
    intent = classify_brief(instruction)
    energy = intent["energy"]
    processors = {layer.processor for layer in plan.layers}

    if energy == "high":
        plan.global_parameters.overall_intensity = max(
            plan.global_parameters.overall_intensity, 0.88
        )
        plan.global_parameters.source_preservation = min(
            plan.global_parameters.source_preservation, 0.22
        )
        for layer in plan.layers:
            if layer.processor == "passthrough":
                layer.volume = min(layer.volume, 0.35)
                layer.intensity = min(layer.intensity, 0.2)
            else:
                layer.intensity = max(layer.intensity, 0.8)
                layer.volume = max(layer.volume, 0.85)
        # Ensure a hardcore-ish palette is present.
        _ensure_layer(plan, "pulse", "stutter", intensity=0.9, start_ratio=0.15)
        _ensure_layer(plan, "crush", "destroy", intensity=0.92, start_ratio=0.35)
        _ensure_layer(plan, "riser", "pitch_warp", intensity=0.85, start_ratio=0.0)
        if "feedback" not in processors and "comb" not in processors:
            _ensure_layer(plan, "pressure", "feedback", intensity=0.82, start_ratio=0.45)
        _ensure_peak_section_uses_aggressive_layers(plan)

    elif energy == "low":
        plan.global_parameters.overall_intensity = min(
            plan.global_parameters.overall_intensity, 0.45
        )
        plan.global_parameters.source_preservation = max(
            plan.global_parameters.source_preservation, 0.55
        )
        for layer in plan.layers:
            if layer.processor in {"destroy", "collapse"}:
                layer.intensity = min(layer.intensity, 0.45)
                layer.volume = min(layer.volume, 0.6)

    if intent["glitch"] and "stutter" not in {layer.processor for layer in plan.layers}:
        _ensure_layer(plan, "glitch", "stutter", intensity=0.85, start_ratio=0.2)

    if intent["metallic"] and not {"comb", "ring_mod"} & {
        layer.processor for layer in plan.layers
    }:
        _ensure_layer(plan, "metal", "comb", intensity=0.75, start_ratio=0.1)

    # Keep primary_mode aligned with something actually present.
    present = {layer.processor for layer in plan.layers}
    if plan.global_parameters.primary_mode not in present and present:
        preferred = (
            "destroy"
            if "destroy" in present
            else ("stutter" if "stutter" in present else next(iter(present)))
        )
        plan.global_parameters.primary_mode = preferred

    return plan


def _ensure_layer(
    plan: ProductionPlan,
    layer_id: str,
    processor: str,
    *,
    intensity: float,
    start_ratio: float,
) -> None:
    if any(layer.processor == processor for layer in plan.layers):
        return
    # Unique id.
    existing = {layer.id for layer in plan.layers}
    final_id = layer_id
    suffix = 2
    while final_id in existing:
        final_id = f"{layer_id}_{suffix}"
        suffix += 1
    start = max(0.0, plan.duration_seconds * start_ratio)
    plan.layers.append(
        AudioLayer(
            id=final_id,
            processor=processor,
            intensity=intensity,
            volume=1.0,
            start=start,
            end=plan.duration_seconds,
            notes=f"brief-intent:{processor}",
        )
    )
    # Attach to later/high-energy sections when available.
    if plan.sections:
        target = max(plan.sections, key=lambda section: section.energy)
        if final_id not in target.active_layers:
            target.active_layers.append(final_id)
        # Also enable on the last section for a peak ending.
        last = plan.sections[-1]
        if final_id not in last.active_layers:
            last.active_layers.append(final_id)


def _ensure_peak_section_uses_aggressive_layers(plan: ProductionPlan) -> None:
    if not plan.sections:
        return
    aggressive = [
        layer.id
        for layer in plan.layers
        if layer.processor in {"destroy", "stutter", "feedback", "ring_mod", "collapse"}
    ]
    if not aggressive:
        return
    peak = max(plan.sections, key=lambda section: (section.energy, section.end))
    for layer_id in aggressive:
        if layer_id not in peak.active_layers:
            peak.active_layers.append(layer_id)
    # If sections never gated anything, leave active_layers; executor handles both.
    if len(plan.sections) >= 2 and all(not s.active_layers for s in plan.sections[:-1]):
        # Build a simple build→peak gating.
        early_ids = [
            layer.id
            for layer in plan.layers
            if layer.processor in {"granular", "pitch_warp", "passthrough", "comb"}
        ]
        for section in plan.sections[:-1]:
            section.active_layers = list(early_ids) or [plan.layers[0].id]
        plan.sections[-1].active_layers = list(
            {layer.id for layer in plan.layers}
        )
