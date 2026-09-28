"""Granular remix strategy."""

from __future__ import annotations

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.configuration import RemixParameters
from noise_remix.remix.base import intensity_lerp, register
from noise_remix.seed import make_rng


@register
class GranularMode:
    name = "granular"

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
        source_duration = analysis.duration
        segments = analysis.segments or []

        grain_duration = intensity_lerp(intensity, 0.12, 0.025)
        density = intensity_lerp(intensity, 8.0, 45.0)  # grains per second
        position_jitter = intensity_lerp(intensity, 0.0, 0.35)
        rate_jitter = intensity_lerp(intensity, 0.0, 0.55)
        reverse_probability = intensity_lerp(intensity, 0.0, 0.45)
        pan_jitter = intensity_lerp(intensity, 0.1, 1.0)
        amp_jitter = intensity_lerp(intensity, 0.05, 0.35)

        n_grains = max(1, int(duration * density))
        max_grains = 3000
        if n_grains > max_grains:
            n_grains = max_grains
            spacing = duration / float(n_grains)
        else:
            spacing = 1.0 / density

        grains: list[dict[str, float | bool]] = []
        for index in range(n_grains):
            onset = index * spacing
            if onset >= duration:
                break
            if segments:
                segment = segments[rng.randrange(len(segments))]
                local = rng.random() * max(1e-6, segment.duration - grain_duration)
                buf_pos = segment.start + local
            else:
                max_pos = max(0.0, source_duration - grain_duration)
                buf_pos = rng.random() * max_pos

            buf_pos = min(
                max(0.0, buf_pos + rng.uniform(-position_jitter, position_jitter)),
                max(0.0, source_duration - 0.001),
            )
            rate = 1.0 + rng.uniform(-rate_jitter, rate_jitter)
            rate = max(0.25, min(2.5, rate))
            reverse = rng.random() < reverse_probability
            if reverse:
                rate = -abs(rate)
            pan = rng.uniform(-pan_jitter, pan_jitter)
            overlap = max(1.0, density * grain_duration)
            amp_scale = 0.7 / (overlap**0.5)
            amp = max(
                0.03,
                amp_scale
                * (1.0 - amp_jitter * 0.35 + rng.uniform(-amp_jitter, amp_jitter) * 0.25),
            )
            grains.append(
                {
                    "onset": round(onset, 6),
                    "buf_pos": round(buf_pos, 6),
                    "dur": round(grain_duration, 6),
                    "rate": round(rate, 6),
                    "pan": round(max(-1.0, min(1.0, pan)), 6),
                    "amp": round(max(0.02, min(0.5, amp)), 6),
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
                "grain_duration": grain_duration,
                "density": density,
                "position_jitter": position_jitter,
                "rate_jitter": rate_jitter,
                "reverse_probability": reverse_probability,
                "grains": grains,
            },
        )
