"""Beat-aware timing: snap plan boundaries and build crossfaded layer windows."""

from __future__ import annotations

from typing import Any

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.production import ProductionPlan, Transition


def align_plan_to_analysis(
    plan: ProductionPlan,
    analysis: AudioAnalysis,
    *,
    default_crossfade: float = 0.85,
) -> ProductionPlan:
    """Snap section boundaries to transients/segments and ensure crossfade transitions."""
    duration = min(plan.duration_seconds, analysis.duration)
    plan.duration_seconds = duration
    grid = _timing_grid(analysis, duration)
    if not plan.sections:
        return plan

    # Snap interior boundaries; keep 0 and duration anchored.
    snapped: list[tuple[float, float]] = []
    for index, section in enumerate(plan.sections):
        start = 0.0 if index == 0 else _snap_time(section.start, grid, duration)
        end = (
            duration
            if index == len(plan.sections) - 1
            else _snap_time(section.end, grid, duration)
        )
        snapped.append((start, end))

    # Enforce monotonic non-empty spans.
    cursor = 0.0
    min_span = 0.12
    for index, section in enumerate(plan.sections):
        start, end = snapped[index]
        start = max(cursor, start)
        if index < len(plan.sections) - 1:
            end = max(start + min_span, end)
            # Leave room for remaining sections.
            remaining = len(plan.sections) - index - 1
            end = min(end, duration - remaining * min_span)
        else:
            end = duration
        if end <= start:
            end = min(duration, start + min_span)
        section.start = round(start, 6)
        section.end = round(end, 6)
        cursor = section.end

    # Ensure adjacent sections share exact boundaries.
    for index in range(len(plan.sections) - 1):
        boundary = plan.sections[index].end
        plan.sections[index + 1].start = boundary

    fade = _resolve_crossfade_seconds(plan, duration, default_crossfade)
    _ensure_crossfade_transitions(plan, fade)
    return plan


def layer_windows_with_crossfades(
    plan: ProductionPlan,
    *,
    duration: float,
    default_crossfade: float = 0.85,
) -> dict[str, list[dict[str, float]]]:
    """Build per-layer play windows with fade_in / fade_out for smooth section changes.

    Each window dict: ``{start, end, fade_in, fade_out}`` where ``end`` already includes
    the fade-out tail that overlaps the next section (classic crossfade).
    """
    fade = _resolve_crossfade_seconds(plan, duration, default_crossfade)
    any_gating = any(section.active_layers for section in plan.sections)
    result: dict[str, list[dict[str, float]]] = {layer.id: [] for layer in plan.layers}

    if not any_gating:
        for layer in plan.layers:
            start = max(0.0, layer.start)
            end = layer.end if layer.end is not None else duration
            end = min(duration, end)
            if end - start < 0.02:
                continue
            result[layer.id].append(
                _window(start, end, fade_in=min(fade, 0.35), fade_out=min(fade, 0.35), duration=duration)
            )
        return result

    # Boolean presence per section for each layer.
    for layer in plan.layers:
        active_flags = [
            layer.id in section.active_layers for section in plan.sections
        ]
        index = 0
        while index < len(plan.sections):
            if not active_flags[index]:
                index += 1
                continue
            start_index = index
            while index + 1 < len(plan.sections) and active_flags[index + 1]:
                index += 1
            end_index = index
            gate_start = plan.sections[start_index].start
            gate_end = plan.sections[end_index].end
            # Crossfade overlap only when neighbor sections exist / layer turns off.
            entering = start_index == 0 or not active_flags[start_index - 1]
            leaving = end_index == len(plan.sections) - 1 or not active_flags[end_index + 1]
            fade_in = fade if entering else min(0.2, fade * 0.25)
            fade_out = fade if leaving else min(0.2, fade * 0.25)
            # Intersect with layer's own span.
            layer_end = layer.end if layer.end is not None else duration
            start = max(gate_start, layer.start)
            end = min(gate_end, layer_end, duration)
            if end - start >= 0.02:
                result[layer.id].append(
                    _window(start, end, fade_in=fade_in, fade_out=fade_out, duration=duration)
                )
            index += 1
    return result


def snap_events_to_transients(
    events: list[dict[str, Any]],
    *,
    analysis: AudioAnalysis,
    window_start: float,
    window_end: float,
    strength: float = 0.65,
) -> list[dict[str, Any]]:
    """Pull event onsets toward nearby transients (stutter/hits land on beats)."""
    if not events:
        return events
    grid = _timing_grid(analysis, analysis.duration)
    if len(grid) < 2:
        return events
    strength = max(0.0, min(1.0, strength))
    snapped: list[dict[str, Any]] = []
    for item in events:
        event = dict(item)
        onset = float(event["onset"])
        if onset < window_start or onset >= window_end:
            continue
        target = _snap_time(onset, grid, analysis.duration)
        # Keep within window; blend toward grid.
        blended = onset * (1.0 - strength) + target * strength
        blended = min(max(blended, window_start), max(window_start, window_end - 0.001))
        event["onset"] = round(blended, 6)
        snapped.append(event)
    return snapped


def envelope_gain_at(
    *,
    time: float,
    start: float,
    end: float,
    fade_in: float,
    fade_out: float,
) -> float:
    """Piecewise-linear gain for a crossfaded window (1.0 at full level)."""
    if time < start or time > end:
        return 0.0
    fade_in = max(0.0, fade_in)
    fade_out = max(0.0, fade_out)
    # Full-level region.
    full_start = start + fade_in
    full_end = end - fade_out
    if full_end < full_start:
        # Short window: triangular fade.
        mid = (start + end) * 0.5
        if time <= mid:
            return 0.0 if fade_in <= 0 else max(0.0, min(1.0, (time - start) / max(fade_in, 1e-6)))
        return 0.0 if fade_out <= 0 else max(0.0, min(1.0, (end - time) / max(fade_out, 1e-6)))
    if time < full_start:
        return 0.0 if fade_in <= 0 else max(0.0, min(1.0, (time - start) / fade_in))
    if time > full_end:
        return 0.0 if fade_out <= 0 else max(0.0, min(1.0, (end - time) / fade_out))
    return 1.0


def _window(
    start: float,
    end: float,
    *,
    fade_in: float,
    fade_out: float,
    duration: float,
) -> dict[str, float]:
    fade_in = max(0.05, min(fade_in, max(0.05, (end - start) * 0.45)))
    fade_out = max(0.05, min(fade_out, 2.5))
    # Extend end so release overlaps the next section.
    play_end = min(duration, end + fade_out)
    # Clamp fades to playable length.
    total = max(0.05, play_end - start)
    fade_in = min(fade_in, total * 0.45)
    fade_out = min(fade_out, total * 0.45)
    return {
        "start": round(start, 6),
        "end": round(play_end, 6),
        "gate_end": round(end, 6),
        "fade_in": round(fade_in, 6),
        "fade_out": round(fade_out, 6),
    }


def _timing_grid(analysis: AudioAnalysis, duration: float) -> list[float]:
    points = {0.0, duration}
    for transient in analysis.transients:
        if 0.0 < transient < duration:
            points.add(float(transient))
    for segment in analysis.segments:
        if 0.0 < segment.start < duration:
            points.add(float(segment.start))
        if 0.0 < segment.end < duration:
            points.add(float(segment.end))
    # Light beat grid from estimated BPM when available.
    bpm = analysis.estimated_bpm
    if bpm is not None and 40.0 <= bpm <= 220.0:
        step = 60.0 / bpm
        t = 0.0
        while t < duration:
            points.add(round(t, 6))
            t += step
    return sorted(points)


def _snap_time(time: float, grid: list[float], duration: float) -> float:
    time = max(0.0, min(duration, time))
    if not grid:
        return time
    nearest = min(grid, key=lambda point: abs(point - time))
    # Only snap when reasonably close (avoid huge jumps).
    if abs(nearest - time) <= 0.75:
        return float(nearest)
    return time


def _resolve_crossfade_seconds(
    plan: ProductionPlan,
    duration: float,
    default_crossfade: float,
) -> float:
    explicit = [
        float(transition.duration)
        for transition in plan.transitions
        if transition.kind in {"crossfade", "gradual", "layer_in", "layer_out"}
        and transition.duration > 0
    ]
    fade = max(explicit) if explicit else default_crossfade
    # Scale mildly with track length; keep musical.
    fade = max(0.35, min(2.0, fade))
    if duration < 3.0:
        fade = min(fade, max(0.2, duration * 0.15))
    return fade


def _ensure_crossfade_transitions(plan: ProductionPlan, fade: float) -> None:
    if len(plan.sections) < 2:
        return
    existing_at = {round(transition.at, 3) for transition in plan.transitions}
    for index in range(len(plan.sections) - 1):
        boundary = plan.sections[index].end
        key = round(boundary, 3)
        if key in existing_at:
            # Upgrade zero-duration transitions to audible fades.
            for transition in plan.transitions:
                if abs(transition.at - boundary) <= 0.02 and transition.duration <= 0:
                    transition.duration = fade
                    if transition.kind in {"cut", "abrupt"}:
                        transition.kind = "crossfade"
            continue
        plan.transitions.append(
            Transition(
                at=boundary,
                kind="crossfade",
                description=f"Auto crossfade into {plan.sections[index + 1].name}",
                duration=fade,
            )
        )
