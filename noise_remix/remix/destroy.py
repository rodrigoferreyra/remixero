"""Destroy remix strategy — aggressive fragmentation and degradation."""

from __future__ import annotations

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.configuration import RemixParameters
from noise_remix.remix.base import register
from noise_remix.remix.fragments import build_fragment_cloud
from noise_remix.seed import make_rng


@register
class DestroyMode:
    name = "destroy"

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
        events, stats = build_fragment_cloud(
            analysis=analysis,
            rng=rng,
            duration=duration,
            intensity=intensity,
            density_range=(6.0, 65.0),
            dur_range=(0.18, 0.02),
            rate_jitter_range=(0.15, 2.1),
            reverse_range=(0.1, 0.75),
            distort_range=(0.15, 0.95),
            position_jitter_range=(0.05, 0.75),
            lpf_range=(12000.0, 1800.0),
            hpf_range=(40.0, 900.0),
            amp_base=0.28,
            progress_curve=False,
        )
        return RemixParameters(
            mode=self.name,
            intensity=intensity,
            seed=seed,
            duration=duration,
            sample_rate=analysis.sample_rate,
            channels=analysis.channels,
            details={**stats, "events": events, "engine": "fragments"},
        )
