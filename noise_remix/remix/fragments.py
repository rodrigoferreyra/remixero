"""Shared fragment-cloud helpers for aggressive remix modes."""

from __future__ import annotations

from random import Random

from noise_remix.models.analysis import AudioAnalysis, Segment
from noise_remix.remix.base import intensity_lerp


def pick_buf_pos(
    rng: Random,
    *,
    segments: list[Segment],
    source_duration: float,
    grain_duration: float,
    position_jitter: float,
) -> float:
    if segments:
        segment = segments[rng.randrange(len(segments))]
        local = rng.random() * max(1e-6, segment.duration - grain_duration)
        buf_pos = segment.start + local
    else:
        max_pos = max(0.0, source_duration - grain_duration)
        buf_pos = rng.random() * max_pos
    buf_pos = buf_pos + rng.uniform(-position_jitter, position_jitter)
    return min(max(0.0, buf_pos), max(0.0, source_duration - 0.001))


def build_fragment_cloud(
    *,
    analysis: AudioAnalysis,
    rng: Random,
    duration: float,
    intensity: float,
    density_range: tuple[float, float],
    dur_range: tuple[float, float],
    rate_jitter_range: tuple[float, float],
    reverse_range: tuple[float, float],
    distort_range: tuple[float, float],
    position_jitter_range: tuple[float, float],
    lpf_range: tuple[float, float],
    hpf_range: tuple[float, float],
    amp_base: float = 0.25,
    progress_curve: bool = False,
    max_events: int = 3000,
) -> tuple[list[dict[str, float]], dict[str, float]]:
    """Build timed buffer fragments with optional time-evolving collapse behavior."""
    density = intensity_lerp(intensity, *density_range)
    base_dur = intensity_lerp(intensity, *dur_range)
    rate_jitter = intensity_lerp(intensity, *rate_jitter_range)
    reverse_p = intensity_lerp(intensity, *reverse_range)
    distort = intensity_lerp(intensity, *distort_range)
    position_jitter = intensity_lerp(intensity, *position_jitter_range)
    lpf = intensity_lerp(intensity, *lpf_range)
    hpf = intensity_lerp(intensity, *hpf_range)

    n_events = max(1, int(duration * density))
    if n_events > max_events:
        n_events = max_events
        spacing = duration / float(n_events)
    else:
        spacing = 1.0 / density

    segments = analysis.segments or []
    source_duration = analysis.duration
    events: list[dict[str, float]] = []

    for index in range(n_events):
        onset = index * spacing
        if onset >= duration:
            break
        progress = onset / duration if duration > 0 else 0.0
        if progress_curve:
            # Collapse: tighten and darken over time.
            local_dur = base_dur * (1.0 - 0.75 * progress)
            local_density_boost = 1.0 + progress * 2.0
            local_lpf = lpf * (1.0 - 0.7 * progress)
            local_hpf = hpf + (1200.0 * progress)
            local_distort = min(1.0, distort + progress * 0.45)
            # Occasional denser bursts later.
            if rng.random() < progress * 0.35:
                onset = min(duration - 0.001, onset + rng.uniform(0.0, spacing / local_density_boost))
        else:
            local_dur = base_dur * rng.uniform(0.6, 1.4)
            local_lpf = lpf * rng.uniform(0.7, 1.2)
            local_hpf = hpf * rng.uniform(0.5, 1.5)
            local_distort = min(1.0, distort * rng.uniform(0.5, 1.3))

        local_dur = max(0.012, local_dur)
        buf_pos = pick_buf_pos(
            rng,
            segments=segments,
            source_duration=source_duration,
            grain_duration=local_dur,
            position_jitter=position_jitter,
        )
        rate = 1.0 + rng.uniform(-rate_jitter, rate_jitter)
        rate = max(0.15, min(3.5, rate))
        if rng.random() < reverse_p:
            rate = -abs(rate)

        overlap = max(1.0, density * local_dur)
        amp = max(0.03, (amp_base / (overlap**0.5)) * rng.uniform(0.7, 1.2))
        pan = rng.uniform(-1.0, 1.0)

        events.append(
            {
                "onset": round(onset, 6),
                "buf_pos": round(buf_pos, 6),
                "dur": round(local_dur, 6),
                "rate": round(rate, 6),
                "pan": round(pan, 6),
                "amp": round(min(0.55, amp), 6),
                "distort": round(local_distort, 6),
                "lpf": round(max(200.0, min(18000.0, local_lpf)), 3),
                "hpf": round(max(20.0, min(5000.0, local_hpf)), 3),
            }
        )

    stats = {
        "density": density,
        "fragment_duration": base_dur,
        "rate_jitter": rate_jitter,
        "reverse_probability": reverse_p,
        "distort": distort,
        "lpf": lpf,
        "hpf": hpf,
        "position_jitter": position_jitter,
    }
    return events, stats
