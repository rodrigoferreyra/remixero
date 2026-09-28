"""Pitch-warping remix strategy — continuous PitchShift / rate mangling."""

from __future__ import annotations

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.configuration import RemixParameters
from noise_remix.remix.base import intensity_lerp, register
from noise_remix.seed import make_rng


@register
class PitchWarpMode:
    name = "pitch_warp"

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

        # pitch_ratio: 0.5 = octave down, 2.0 = octave up
        pitch_ratio = intensity_lerp(intensity, 0.85, 0.35 if rng.random() < 0.5 else 1.8)
        pitch_ratio = max(0.25, min(2.5, pitch_ratio * rng.uniform(0.9, 1.1)))
        pitch_dispersion = intensity_lerp(intensity, 0.0, 0.18)
        time_dispersion = intensity_lerp(intensity, 0.0, 0.12)
        rate = intensity_lerp(intensity, 1.0, 0.7 if pitch_ratio < 1.0 else 1.25)
        rate = max(0.4, min(1.6, rate * rng.uniform(0.92, 1.08)))
        drive = intensity_lerp(intensity, 1.0, 2.8)
        wet = intensity_lerp(intensity, 0.4, 0.95)

        return RemixParameters(
            mode=self.name,
            intensity=intensity,
            seed=seed,
            duration=duration,
            sample_rate=analysis.sample_rate,
            channels=analysis.channels,
            details={
                "engine": "pitch_warp",
                "pitch_ratio": round(pitch_ratio, 6),
                "pitch_dispersion": round(pitch_dispersion, 6),
                "time_dispersion": round(time_dispersion, 6),
                "playback_rate": round(rate, 6),
                "drive": round(drive, 6),
                "wet": round(wet, 6),
            },
        )
