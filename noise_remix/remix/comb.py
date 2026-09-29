"""Comb / resonator remix strategy."""

from __future__ import annotations

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.configuration import RemixParameters
from noise_remix.remix.base import intensity_lerp, register
from noise_remix.remix.chaos import attach_rand_depth, rand_depth
from noise_remix.seed import make_rng


@register
class CombMode:
    name = "comb"

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
        depth = rand_depth(intensity)

        delay_spread = 0.15 + 0.25 * depth
        delay_time = intensity_lerp(intensity, 0.012, 0.09) * rng.uniform(
            1.0 - delay_spread, 1.0 + delay_spread
        )
        delay_time = max(0.005, min(0.2, delay_time))
        decay = intensity_lerp(intensity, 0.4, 4.5) * rng.uniform(0.85, 1.15)
        decay = max(0.2, min(6.0, decay))
        wet = intensity_lerp(intensity, 0.25, 0.85)
        rate = 1.0 + rng.uniform(-0.08 - 0.1 * depth, 0.08 + 0.1 * depth) * intensity
        rate = max(0.5, min(1.5, rate))
        hpf = intensity_lerp(intensity, 40.0, 180.0)
        lpf = intensity_lerp(intensity, 12000.0, 3500.0)

        return RemixParameters(
            mode=self.name,
            intensity=intensity,
            seed=seed,
            duration=duration,
            sample_rate=analysis.sample_rate,
            channels=analysis.channels,
            details=attach_rand_depth(
                {
                    "engine": "comb",
                    "delay_time": round(delay_time, 6),
                    "decay": round(decay, 6),
                    "wet": round(wet, 6),
                    "playback_rate": round(rate, 6),
                    "hpf": round(hpf, 3),
                    "lpf": round(lpf, 3),
                },
                intensity,
            ),
        )
