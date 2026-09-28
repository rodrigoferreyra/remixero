"""Collapse remix strategy — progressive densification and degradation."""

from __future__ import annotations

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.configuration import RemixParameters
from noise_remix.remix.base import intensity_lerp, register
from noise_remix.remix.fragments import build_fragment_cloud
from noise_remix.seed import make_rng


@register
class CollapseMode:
    name = "collapse"

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
            density_range=(5.0, 40.0),
            dur_range=(0.22, 0.04),
            rate_jitter_range=(0.05, 0.9),
            reverse_range=(0.05, 0.4),
            distort_range=(0.05, 0.75),
            position_jitter_range=(0.02, 0.35),
            lpf_range=(14000.0, 2500.0),
            hpf_range=(30.0, 400.0),
            amp_base=0.26,
            progress_curve=True,
        )
        # Bounded late-stage feedback coloration for the SC layer.
        feedback_amount = intensity_lerp(intensity, 0.05, 0.55)
        return RemixParameters(
            mode=self.name,
            intensity=intensity,
            seed=seed,
            duration=duration,
            sample_rate=analysis.sample_rate,
            channels=analysis.channels,
            details={
                **stats,
                "events": events,
                "engine": "fragments",
                "feedback_amount": feedback_amount,
            },
        )
