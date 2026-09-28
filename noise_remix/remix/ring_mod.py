"""Ring-modulation remix strategy."""

from __future__ import annotations

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.configuration import RemixParameters
from noise_remix.remix.base import intensity_lerp, register
from noise_remix.seed import make_rng


@register
class RingModMode:
    name = "ring_mod"

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

        # Prefer inharmonic carrier frequencies for metallic / noise character.
        freq = intensity_lerp(intensity, 40.0, 900.0) * rng.uniform(0.8, 1.25)
        freq = max(20.0, min(2000.0, freq))
        depth = intensity_lerp(intensity, 0.35, 1.0)
        rate = 1.0 + rng.uniform(-0.12, 0.12) * intensity
        rate = max(0.4, min(1.8, rate))
        drive = intensity_lerp(intensity, 1.0, 3.5)
        lpf = intensity_lerp(intensity, 14000.0, 2800.0)

        return RemixParameters(
            mode=self.name,
            intensity=intensity,
            seed=seed,
            duration=duration,
            sample_rate=analysis.sample_rate,
            channels=analysis.channels,
            details={
                "engine": "ring_mod",
                "mod_freq": round(freq, 3),
                "depth": round(depth, 6),
                "playback_rate": round(rate, 6),
                "drive": round(drive, 6),
                "lpf": round(lpf, 3),
            },
        )
