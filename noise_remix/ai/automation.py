"""Apply production-plan automation events to compiled layer windows."""

from __future__ import annotations

from typing import Any

from noise_remix.models.production import AutomationEvent, AudioLayer, ProductionPlan

# Targets we know how to map into render parameters.
_CONTINUOUS_TARGETS = {
    "volume",
    "amp",
    "feedback",
    "pitch_ratio",
    "mod_freq",
    "wet",
    "drive",
    "depth",
    "decay",
    "delay_time",
    "lpf",
    "hpf",
    "intensity",
}
_EVENT_TARGETS = {"volume", "amp", "density", "intensity"}


def collect_automation(
    plan: ProductionPlan,
    layer: AudioLayer,
) -> list[AutomationEvent]:
    """Merge layer automation with section automation that names this layer's params."""
    events = list(layer.automation)
    for section in plan.sections:
        if section.active_layers and layer.id not in section.active_layers:
            continue
        for event in section.automation:
            # Section automation applies to active layers in that span.
            if section.start <= event.time <= section.end:
                events.append(event)
    events.sort(key=lambda item: item.time)
    return events


def apply_automation_to_layer_spec(
    spec: dict[str, Any],
    *,
    events: list[AutomationEvent],
) -> dict[str, Any]:
    """Mutate a compiled layer spec using automation breakpoints."""
    if not events:
        return spec
    start = float(spec["start"])
    end = float(spec["end"])
    details = spec.setdefault("details", {})
    if not isinstance(details, dict):
        details = {}
        spec["details"] = details

    # Continuous param overrides from value at window midpoint (or last event before).
    mid = (start + min(end, start + (end - start) * 0.5)) 
    for target in _CONTINUOUS_TARGETS:
        if target in {"volume", "amp", "density"}:
            continue
        value = _value_at(events, target=target, time=mid, default=None)
        if value is None:
            continue
        mapped = _map_target(target, value)
        if mapped is None:
            continue
        key, number = mapped
        details[key] = number
        if key == "intensity":
            spec["intensity"] = number

    # Volume / amp curve for continuous synths and event scaling.
    volume_points = _series(events, targets=("volume", "amp"), start=start, end=end)
    if volume_points:
        spec["volume_env"] = volume_points
        # Scale base volume by average envelope.
        avg = sum(point[1] for point in volume_points) / len(volume_points)
        spec["volume"] = float(spec.get("volume") or 1.0) * max(0.05, min(2.0, avg))

    # Event engines: scale amps by automation at onset; density via keep probability.
    kind = spec.get("kind")
    if kind in {"grains", "fragments"} and spec.get("events"):
        density_scale = _value_at(events, target="density", time=mid, default=1.0)
        intensity_scale = _value_at(events, target="intensity", time=mid, default=None)
        kept: list[dict[str, Any]] = []
        for index, item in enumerate(spec["events"]):
            onset = float(item["onset"])
            gain = _value_at(events, target="volume", time=onset, default=None)
            if gain is None:
                gain = _value_at(events, target="amp", time=onset, default=1.0)
            gain = max(0.0, min(2.0, float(gain)))  # type: ignore[arg-type]
            if intensity_scale is not None:
                gain *= 0.5 + 0.5 * max(0.0, min(1.0, float(intensity_scale)))
            # Density < 1 randomly thins using deterministic stride.
            dens = 1.0 if density_scale is None else max(0.15, min(2.0, float(density_scale)))
            if dens < 1.0:
                keep_every = max(1, int(round(1.0 / dens)))
                if index % keep_every != 0:
                    continue
            event = dict(item)
            event["amp"] = round(float(event.get("amp", 0.2)) * gain, 6)
            if event["amp"] <= 0.01:
                continue
            kept.append(event)
        # Density > 1: duplicate nearby hits lightly.
        if density_scale is not None and float(density_scale) > 1.15 and kept:
            extra: list[dict[str, Any]] = []
            for item in kept[::2]:
                twin = dict(item)
                twin["onset"] = round(float(item["onset"]) + 0.03, 6)
                twin["amp"] = round(float(item["amp"]) * 0.7, 6)
                if twin["onset"] < end:
                    extra.append(twin)
            kept.extend(extra)
            kept.sort(key=lambda item: float(item["onset"]))
        spec["events"] = kept
    return spec


def _map_target(target: str, value: float) -> tuple[str, float] | None:
    target = target.lower().strip()
    if target == "intensity":
        return "intensity", max(0.0, min(1.0, value))
    if target in _CONTINUOUS_TARGETS and target not in {"volume", "amp", "density"}:
        return target, float(value)
    return None


def _series(
    events: list[AutomationEvent],
    *,
    targets: tuple[str, ...],
    start: float,
    end: float,
) -> list[list[float]]:
    relevant = [
        event
        for event in events
        if event.target.lower() in targets and start - 1e-6 <= event.time <= end + 1e-6
    ]
    if not relevant:
        return []
    points = [[start, _value_at(events, target=targets[0], time=start, default=1.0)]]
    for event in relevant:
        points.append([float(event.time), float(event.value)])
    points.append([end, _value_at(events, target=targets[0], time=end, default=points[-1][1])])
    # Normalize times relative to start for SC Env.
    return [[round(t - start, 6), round(max(0.0, min(2.0, v)), 6)] for t, v in points]


def _value_at(
    events: list[AutomationEvent],
    *,
    target: str,
    time: float,
    default: float | None,
) -> float | None:
    target = target.lower()
    aliases = {target}
    if target == "volume":
        aliases.add("amp")
    if target == "amp":
        aliases.add("volume")
    relevant = [event for event in events if event.target.lower() in aliases]
    if not relevant:
        return default
    # Step/hold previous; linear blend between neighbors.
    before = [event for event in relevant if event.time <= time]
    after = [event for event in relevant if event.time > time]
    if not before:
        return float(after[0].value) if after else default
    if not after or before[-1].curve == "step":
        return float(before[-1].value)
    left = before[-1]
    right = after[0]
    span = right.time - left.time
    if span <= 1e-9:
        return float(right.value)
    alpha = (time - left.time) / span
    if right.curve == "exponential" or left.curve == "exponential":
        alpha = alpha**2
    return float(left.value) + (float(right.value) - float(left.value)) * alpha
