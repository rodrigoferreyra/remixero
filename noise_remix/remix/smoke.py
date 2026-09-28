"""Smoke / pass-through mode (pipeline verification)."""

from __future__ import annotations

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.configuration import RemixParameters
from noise_remix.remix.base import register


@register
class SmokeMode:
    name = "smoke"

    def generate(
        self,
        *,
        analysis: AudioAnalysis,
        intensity: float,
        seed: int,
        duration: float,
    ) -> RemixParameters:
        del intensity  # pass-through ignores intensity by design
        return RemixParameters(
            mode=self.name,
            intensity=0.0,
            seed=seed,
            duration=duration,
            sample_rate=analysis.sample_rate,
            channels=analysis.channels,
            details={"passthrough": True},
        )
