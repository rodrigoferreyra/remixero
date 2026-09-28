"""Repair incomplete or inconsistent AI production-plan payloads."""

from __future__ import annotations

from typing import Any

from noise_remix.ai.registry import CAPABILITY_REGISTRY
from noise_remix.errors import ProductionPlanError
from noise_remix.models.production import ProductionPlan


def coerce_plan_payload(
    payload: object,
    *,
    default_duration: float,
    default_primary_mode: str = "destroy",
) -> dict[str, Any]:
    """Normalize raw LLM JSON into something ProductionPlan can validate.

    LLMs frequently omit required fields, wrap the object, or use free-form
    section/layer shapes. Repair what we can; raise only when the payload is
    unusable.
    """
    data = _unwrap_payload(payload)
    if not isinstance(data, dict):
        raise ProductionPlanError(
            "Production plan payload must be a JSON object."
        )

    data = dict(data)

    if not str(data.get("title") or "").strip():
        data["title"] = "Untitled plan"
    if not str(data.get("description") or "").strip():
        narrative = str(data.get("narrative") or "").strip()
        data["description"] = narrative or "AI production plan"

    duration = _as_positive_float(data.get("duration_seconds"), default_duration)
    data["duration_seconds"] = duration

    data["global_parameters"] = _coerce_global_parameters(
        data.get("global_parameters"),
        default_primary_mode=default_primary_mode,
    )
    data["layers"] = _coerce_layers(data.get("layers"), duration=duration)
    if not data["layers"]:
        raise ProductionPlanError(
            "Production plan has no usable layers after repair."
        )

    layer_ids = [str(layer["id"]) for layer in data["layers"]]
    data["sections"] = _coerce_sections(
        data.get("sections"),
        duration=duration,
        layer_ids=layer_ids,
    )
    if not data["sections"]:
        data["sections"] = [
            {
                "start": 0.0,
                "end": duration,
                "name": "full",
                "energy": 0.5,
                "active_layers": list(layer_ids),
            }
        ]

    if data.get("transitions") is None:
        data["transitions"] = []
    elif not isinstance(data["transitions"], list):
        data["transitions"] = []

    data.setdefault("narrative", "")
    data.setdefault("variation_notes", "")
    return data


def parse_production_plan(
    payload: object,
    *,
    default_duration: float,
    default_primary_mode: str = "destroy",
) -> ProductionPlan:
    """Coerce then Pydantic-validate a production plan payload."""
    repaired = coerce_plan_payload(
        payload,
        default_duration=default_duration,
        default_primary_mode=default_primary_mode,
    )
    try:
        return ProductionPlan.model_validate(repaired)
    except Exception as exc:  # noqa: BLE001
        raise ProductionPlanError(
            f"Production plan failed schema validation: {exc}"
        ) from exc


def resolve_layer_reference(
    reference: str,
    *,
    layer_ids: set[str],
    layers: list[Any],
) -> str | None:
    """Map a section active_layers entry onto a real layer id, if possible."""
    ref = reference.strip()
    if not ref:
        return None
    if ref in layer_ids:
        return ref

    lowered = ref.lower()
    for layer_id in layer_ids:
        if layer_id.lower() == lowered:
            return layer_id

    # Match processor name when the model used role labels like "coloring".
    processor_matches = [
        layer.id
        for layer in layers
        if str(getattr(layer, "processor", "")).lower() == lowered
        or str(getattr(layer, "id", "")).lower().replace("-", "_")
        == lowered.replace("-", "_")
    ]
    if len(processor_matches) == 1:
        return processor_matches[0]

    # Match notes that mention the role name.
    note_matches = [
        layer.id
        for layer in layers
        if lowered in str(getattr(layer, "notes", "")).lower()
    ]
    if len(note_matches) == 1:
        return note_matches[0]

    # Unique substring match against ids.
    substring = [
        layer_id
        for layer_id in layer_ids
        if lowered in layer_id.lower() or layer_id.lower() in lowered
    ]
    if len(substring) == 1:
        return substring[0]

    # Soft role aliases commonly invented by models.
    aliases = {
        "color": ("comb", "ring_mod", "pitch_warp"),
        "coloring": ("comb", "ring_mod", "pitch_warp"),
        "colour": ("comb", "ring_mod", "pitch_warp"),
        "colouring": ("comb", "ring_mod", "pitch_warp"),
        "bed": ("granular", "passthrough", "pitch_warp"),
        "texture": ("granular", "stutter"),
        "destroyer": ("destroy", "collapse", "random"),
        "noise": ("destroy", "random", "stutter"),
        "drone": ("pitch_warp", "feedback", "comb"),
        "glitch": ("stutter", "destroy", "random"),
        "fx": ("feedback", "comb", "ring_mod"),
        "effect": ("feedback", "comb", "ring_mod"),
    }
    for alias, processors in aliases.items():
        if alias in lowered or lowered in alias:
            for processor in processors:
                matches = [
                    layer.id
                    for layer in layers
                    if str(getattr(layer, "processor", "")).lower() == processor
                ]
                if len(matches) == 1:
                    return matches[0]
                if matches:
                    return matches[0]
    return None


def _unwrap_payload(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload
    for key in ("production_plan", "plan", "result", "data"):
        nested = payload.get(key)
        if isinstance(nested, dict) and (
            "layers" in nested or "sections" in nested or "global_parameters" in nested
        ):
            return nested
    return payload


def _coerce_global_parameters(
    raw: object,
    *,
    default_primary_mode: str,
) -> dict[str, Any]:
    allowed = set(CAPABILITY_REGISTRY)
    if not isinstance(raw, dict):
        primary = default_primary_mode if default_primary_mode in allowed else "destroy"
        return {
            "overall_intensity": 0.5,
            "primary_mode": primary,
            "source_preservation": 0.5,
        }
    data = dict(raw)
    primary = str(data.get("primary_mode") or default_primary_mode).strip().lower()
    if primary not in allowed:
        primary = default_primary_mode if default_primary_mode in allowed else "destroy"
    data["primary_mode"] = primary
    data["overall_intensity"] = _clamp01(
        _as_float(data.get("overall_intensity"), 0.5)
    )
    data["source_preservation"] = _clamp01(
        _as_float(data.get("source_preservation"), 0.5)
    )
    return data


def _coerce_layers(raw: object, *, duration: float) -> list[dict[str, Any]]:
    items: list[Any]
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        # {"bed": {...}, "crush": {...}} → list with ids from keys
        items = []
        for key, value in raw.items():
            if isinstance(value, dict):
                layer = dict(value)
                layer.setdefault("id", str(key))
                items.append(layer)
            else:
                items.append({"id": str(key), "processor": str(value)})
    else:
        return []

    allowed = set(CAPABILITY_REGISTRY)
    layers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        layer = dict(item)
        layer_id = str(layer.get("id") or f"layer_{index + 1}").strip()
        if not layer_id:
            layer_id = f"layer_{index + 1}"
        # Deduplicate ids.
        base = layer_id
        suffix = 2
        while layer_id in seen:
            layer_id = f"{base}_{suffix}"
            suffix += 1
        seen.add(layer_id)
        layer["id"] = layer_id

        processor = str(layer.get("processor") or "").strip().lower()
        if processor not in allowed:
            # Try common aliases.
            aliases = {
                "grain": "granular",
                "grains": "granular",
                "smoke": "passthrough",
                "dry": "passthrough",
                "pass_through": "passthrough",
                "ringmod": "ring_mod",
                "ring-modulation": "ring_mod",
                "pitch": "pitch_warp",
                "pitchshift": "pitch_warp",
                "warp": "pitch_warp",
            }
            processor = aliases.get(processor, processor)
        if processor not in allowed:
            continue
        layer["processor"] = processor
        layer["intensity"] = _clamp01(_as_float(layer.get("intensity"), 0.5))
        layer["volume"] = max(0.0, min(2.0, _as_float(layer.get("volume"), 1.0)))
        layer["pan"] = max(-1.0, min(1.0, _as_float(layer.get("pan"), 0.0)))
        layer["start"] = max(0.0, _as_float(layer.get("start"), 0.0))
        end = layer.get("end")
        if end is not None:
            end_f = _as_float(end, duration)
            layer["end"] = end_f if end_f > layer["start"] else None
        layer.setdefault("processing_chain", [])
        layer.setdefault("automation", [])
        layer.setdefault("notes", "")
        if not isinstance(layer["processing_chain"], list):
            layer["processing_chain"] = []
        if not isinstance(layer["automation"], list):
            layer["automation"] = []
        layers.append(layer)
    return layers


def _coerce_sections(
    raw: object,
    *,
    duration: float,
    layer_ids: list[str],
) -> list[dict[str, Any]]:
    items: list[Any]
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = []
        for key, value in raw.items():
            if isinstance(value, dict):
                section = dict(value)
                section.setdefault("name", str(key))
                items.append(section)
    else:
        return []

    sections: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        section = dict(item)
        start = max(0.0, _as_float(section.get("start"), 0.0))
        end = _as_float(section.get("end"), duration)
        if end <= start:
            end = min(duration, start + max(0.05, duration / max(1, len(items))))
        section["start"] = start
        section["end"] = min(duration, end) if duration > 0 else end
        if section["end"] <= section["start"]:
            continue
        name = str(section.get("name") or f"section_{index + 1}").strip()
        section["name"] = name or f"section_{index + 1}"
        section["energy"] = _clamp01(_as_float(section.get("energy"), 0.5))
        section.setdefault("description", "")
        section.setdefault("automation", [])
        if not isinstance(section["automation"], list):
            section["automation"] = []

        active = section.get("active_layers")
        if active is None:
            section["active_layers"] = []
        elif isinstance(active, str):
            section["active_layers"] = [active]
        elif isinstance(active, list):
            section["active_layers"] = [str(x) for x in active if str(x).strip()]
        else:
            section["active_layers"] = list(layer_ids)
        sections.append(section)
    return sections


def _as_float(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _as_positive_float(value: object, default: float) -> float:
    number = _as_float(value, default)
    if number <= 0:
        return default if default > 0 else 1.0
    return number


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
