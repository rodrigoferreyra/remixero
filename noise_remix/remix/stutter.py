"""Stutter / freeze remix strategy — rapid locked buffer slices."""

from __future__ import annotations

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.configuration import RemixParameters
from noise_remix.remix.base import intensity_lerp, register
from noise_remix.remix.fragments import pick_buf_pos
from noise_remix.seed import make_rng


@register
class StutterMode:
    name = "stutter"

    def generate(
        self,
        *,
        analysis: AudioAnalysis,
        intensity: float,
        seed: int,
        duration: float,
    ) -> RemixParameters:
        if not 0.0 <= intensity <= 1.0:
            raise ValueError("intensity must be in [0, 1]")
        rng = make_rng(seed)

        slice_dur = intensity_lerp(intensity, 0.08, 0.018)
        density = intensity_lerp(intensity, 6.0, 28.0)
        hold_probability = intensity_lerp(intensity, 0.35, 0.85)
        rate_jitter = intensity_lerp(intensity, 0.0, 0.35)
        distort = intensity_lerp(intensity, 0.05, 0.55)
        lpf = intensity_lerp(intensity, 14000.0, 4000.0)
        hpf = intensity_lerp(intensity, 40.0, 200.0)

        n_events = max(1, int(duration * density))
        n_events = min(n_events, 3000)
        spacing = duration / float(n_events) if n_events else duration
        segments = analysis.segments or []
        source_duration = analysis.duration

        events: list[dict[str, float]] = []
        held_pos: float | None = None
        for index in range(n_events):
            onset = index * spacing
            if onset >= duration:
                break
            if held_pos is None or rng.random() > hold_probability:
                held_pos = pick_buf_pos(
                    rng,
                    segments=segments,
                    source_duration=source_duration,
                    grain_duration=slice_dur,
                    position_jitter=0.02 * intensity,
                )
            rate = 1.0 + rng.uniform(-rate_jitter, rate_jitter)
            rate = max(0.5, min(2.0, rate))
            if rng.random() < intensity * 0.25:
                rate = -abs(rate)
            pan = rng.uniform(-0.8, 0.8) * intensity_lerp(intensity, 0.2, 1.0)
            amp = 0.22 / max(1.0, (density * slice_dur) ** 0.5)
            amp = max(0.04, min(0.45, amp))
            events.append(
                {
                    "onset": round(onset, 6),
                    "buf_pos": round(held_pos, 6),
                    "dur": round(slice_dur, 6),
                    "rate": round(rate, 6),
                    "pan": round(pan, 6),
                    "amp": round(amp, 6),
                    "distort": round(distort, 6),
                    "lpf": round(lpf, 3),
                    "hpf": round(hpf, 3),
                }
            )

        return RemixParameters(
            mode=self.name,
            intensity=intensity,
            seed=seed,
            duration=duration,
            sample_rate=analysis.sample_rate,
            channels=analysis.channels,
            details={
                "engine": "fragments",
                "slice_dur": round(slice_dur, 6),
                "density": round(density, 6),
                "hold_probability": round(hold_probability, 6),
                "feedback_amount": round(intensity_lerp(intensity, 0.0, 0.25), 6),
                "events": events,
            },
        )
