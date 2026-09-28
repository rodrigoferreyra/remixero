"""Execute a validated ProductionPlan as a multi-layer SuperCollider render."""

from __future__ import annotations

import zlib
from typing import Any

from noise_remix.ai.registry import CAPABILITY_REGISTRY, executable_mode_for
from noise_remix.ai.timing import (
    align_plan_to_analysis,
    envelope_gain_at,
    layer_windows_with_crossfades,
    snap_events_to_transients,
)
from noise_remix.errors import ProductionPlanError
from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.configuration import RemixParameters
from noise_remix.models.production import AudioLayer, ProductionPlan
from noise_remix.remix import get_mode
from noise_remix.remix.feedback import MAX_FEEDBACK

# Event engines: timed grain/fragment lists shifted into the layer window.
_EVENT_KINDS = {
    "grains",
    "fragments",
}


def plan_to_remix_parameters(
    plan: ProductionPlan,
    *,
    analysis: AudioAnalysis,
    seed: int,
) -> RemixParameters:
    """Compile a production plan into layered remix parameters for SuperCollider.

    Section boundaries are snapped to analysis transients/segments. Layer windows
    include crossfade tails so section changes overlap instead of hard-cutting.
    """
    plan = align_plan_to_analysis(plan, analysis)
    duration = min(plan.duration_seconds, analysis.duration)
    if duration <= 0:
        raise ProductionPlanError("Plan duration must be positive.")

    preservation = plan.global_parameters.source_preservation
    overall = plan.global_parameters.overall_intensity
    windows_by_layer = layer_windows_with_crossfades(plan, duration=duration)

    compiled: list[dict[str, Any]] = []
    for layer in plan.layers:
        windows = windows_by_layer.get(layer.id) or []
        for window_index, window in enumerate(windows):
            start = float(window["start"])
            end = float(window["end"])
            if end - start < 0.02:
                continue
            spec = _compile_layer(
                layer=layer,
                analysis=analysis,
                seed=_layer_seed(seed, layer.id, window_index),
                start=start,
                end=end,
                fade_in=float(window["fade_in"]),
                fade_out=float(window["fade_out"]),
                gate_end=float(window.get("gate_end", end)),
                overall_intensity=overall,
                source_preservation=preservation,
            )
            compiled.append(spec)

    if not compiled:
        primary = plan.global_parameters.primary_mode
        try:
            mode_name = executable_mode_for(primary)
        except KeyError as exc:
            raise ProductionPlanError(f"Cannot execute processor '{primary}'") from exc
        intensity = max(0.0, min(1.0, (overall * 0.7) + ((1.0 - preservation) * 0.3)))
        params = get_mode(mode_name).generate(
            analysis=analysis,
            intensity=intensity,
            seed=seed,
            duration=duration,
        )
        params.details = {
            **params.details,
            "ai_primary_mode": primary,
            "ai_title": plan.title,
            "ai_layer_ids": [layer.id for layer in plan.layers],
            "ai_section_count": len(plan.sections),
            "ai_render": "primary_fallback",
        }
        return params

    n_layers = len(compiled)
    mix_scale = 1.0 / max(1.0, n_layers**0.5)
    for spec in compiled:
        spec["volume"] = float(spec["volume"]) * mix_scale

    intensity = max(
        (float(spec.get("intensity") or 0.0) for spec in compiled),
        default=overall,
    )
    intensity = max(0.0, min(1.0, intensity))
    crossfade = 0.0
    if plan.transitions:
        crossfade = max((float(t.duration) for t in plan.transitions), default=0.0)

    return RemixParameters(
        mode="ai_plan",
        intensity=intensity,
        seed=seed,
        duration=duration,
        sample_rate=analysis.sample_rate,
        channels=analysis.channels,
        details={
            "engine": "layered",
            "layers": compiled,
            "ai_primary_mode": plan.global_parameters.primary_mode,
            "ai_title": plan.title,
            "ai_layer_ids": [layer.id for layer in plan.layers],
            "ai_section_count": len(plan.sections),
            "ai_render": "layered",
            "source_preservation": preservation,
            "mix_scale": mix_scale,
            "crossfade_seconds": crossfade,
            "section_bounds": [
                {"name": section.name, "start": section.start, "end": section.end}
                for section in plan.sections
            ],
        },
    )


def _layer_seed(seed: int, layer_id: str, window_index: int) -> int:
    digest = zlib.adler32(f"{layer_id}:{window_index}".encode("utf-8"))
    return int(seed) ^ int(digest)


def _compile_layer(
    *,
    layer: AudioLayer,
    analysis: AudioAnalysis,
    seed: int,
    start: float,
    end: float,
    fade_in: float,
    fade_out: float,
    gate_end: float,
    overall_intensity: float,
    source_preservation: float,
) -> dict[str, Any]:
    try:
        mode_name = executable_mode_for(layer.processor)
    except KeyError as exc:
        raise ProductionPlanError(
            f"Cannot execute processor '{layer.processor}' on layer '{layer.id}'"
        ) from exc

    overrides = _collect_overrides(layer)
    intensity = float(overrides.get("intensity", layer.intensity))
    intensity = max(intensity, overall_intensity * 0.35)
    intensity = max(0.0, min(1.0, (intensity * 0.75) + ((1.0 - source_preservation) * 0.25)))

    # Generate material for the gated span; fades extend beyond gate_end.
    window_dur = max(0.05, gate_end - start)
    mode = get_mode(mode_name)
    params = mode.generate(
        analysis=analysis,
        intensity=intensity,
        seed=seed,
        duration=window_dur,
    )
    _apply_overrides(params.details, overrides, processor=layer.processor)

    kind = _kind_for(mode_name, params.details)
    spec: dict[str, Any] = {
        "id": layer.id,
        "processor": layer.processor,
        "mode": mode_name,
        "kind": kind,
        "intensity": intensity,
        "volume": float(layer.volume),
        "pan": float(layer.pan),
        "start": round(start, 6),
        "end": round(end, 6),
        "fade_in": round(fade_in, 6),
        "fade_out": round(fade_out, 6),
        "details": params.details,
    }

    if kind in _EVENT_KINDS:
        events_key = "grains" if kind == "grains" else "events"
        raw_events = params.details.get(events_key) or []
        shifted: list[dict[str, Any]] = []
        for item in raw_events:
            if not isinstance(item, dict):
                continue
            onset = float(item["onset"]) + start
            if onset >= end:
                continue
            event = dict(item)
            event["onset"] = round(onset, 6)
            event["pan"] = round(
                max(-1.0, min(1.0, float(event.get("pan", 0.0)) * 0.5 + layer.pan * 0.5)),
                6,
            )
            gain = envelope_gain_at(
                time=onset,
                start=start,
                end=end,
                fade_in=fade_in,
                fade_out=fade_out,
            )
            if gain <= 0.02:
                continue
            event["amp"] = round(
                float(event.get("amp", 0.2)) * float(layer.volume) * gain, 6
            )
            shifted.append(event)
        # Prefer musical onsets for hit-oriented engines.
        if layer.processor in {"stutter", "destroy", "random", "collapse"}:
            shifted = snap_events_to_transients(
                shifted,
                analysis=analysis,
                window_start=start,
                window_end=end,
                strength=0.7 if layer.processor == "stutter" else 0.45,
            )
        spec["events"] = shifted
    return spec


def _kind_for(mode_name: str, details: dict[str, Any]) -> str:
    if mode_name == "smoke":
        return "passthrough"
    if mode_name == "granular":
        return "grains"
    if mode_name in {"destroy", "collapse", "random", "stutter"}:
        return "fragments"
    if mode_name in {"feedback", "comb", "ring_mod", "pitch_warp"}:
        return mode_name
    engine = details.get("engine")
    if engine in {"feedback", "comb", "ring_mod", "pitch_warp", "fragments"}:
        return "fragments" if engine == "fragments" else str(engine)
    return mode_name


def _collect_overrides(layer: AudioLayer) -> dict[str, float | int | bool | str]:
    overrides: dict[str, float | int | bool | str] = {}
    for step in layer.processing_chain:
        step_params = step.parameters_as_dict()
        if step.processor == layer.processor:
            overrides.update(step_params)
        else:
            for key, value in step_params.items():
                overrides.setdefault(key, value)
    return overrides


def _apply_overrides(
    details: dict[str, Any],
    overrides: dict[str, float | int | bool | str],
    *,
    processor: str,
) -> None:
    """Patch generated details with explicit plan parameters (clamped)."""
    if not overrides:
        return
    specs = (CAPABILITY_REGISTRY.get(processor) or {}).get("parameters") or {}

    def clamp_key(key: str, value: float) -> float:
        spec = specs.get(key)
        if isinstance(spec, dict) and "min" in spec and "max" in spec:
            return max(float(spec["min"]), min(float(spec["max"]), value))
        return value

    continuous_keys = (
        "feedback",
        "delay_time",
        "drive",
        "decay",
        "wet",
        "mod_freq",
        "depth",
        "pitch_ratio",
        "pitch_dispersion",
        "time_dispersion",
        "playback_rate",
        "lpf",
        "hpf",
        "feedback_amount",
        "hold_probability",
    )
    for key in continuous_keys:
        if key not in overrides:
            continue
        try:
            value = float(overrides[key])
        except (TypeError, ValueError):
            continue
        if key == "feedback":
            value = max(0.0, min(MAX_FEEDBACK, value))
        else:
            value = clamp_key(key, value)
        details[key] = value
