"""Random remix strategy — seeded combination of transformation primitives."""

from __future__ import annotations

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.configuration import RemixParameters
from noise_remix.remix.base import intensity_lerp, register
from noise_remix.remix.fragments import build_fragment_cloud
from noise_remix.seed import make_rng


@register
class RandomMode:
    name = "random"

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

        # Choose a palette of primitives deterministically from the seed.
        use_extreme_rates = rng.random() < intensity_lerp(intensity, 0.2, 0.9)
        use_heavy_distort = rng.random() < intensity_lerp(intensity, 0.15, 0.85)
        use_narrow_band = rng.random() < intensity_lerp(intensity, 0.1, 0.7)
        use_reverse_bias = rng.random() < intensity_lerp(intensity, 0.2, 0.8)
        use_stutter = rng.random() < intensity_lerp(intensity, 0.25, 0.9)

        density_hi = 50.0 if use_stutter else 28.0
        dur_lo = 0.018 if use_stutter else 0.04
        rate_hi = 2.2 if use_extreme_rates else 0.85
        distort_hi = 0.95 if use_heavy_distort else 0.45
        reverse_hi = 0.75 if use_reverse_bias else 0.35
        lpf_lo = 1200.0 if use_narrow_band else 4000.0
        hpf_hi = 1200.0 if use_narrow_band else 400.0

        events, stats = build_fragment_cloud(
            analysis=analysis,
            rng=rng,
            duration=duration,
            intensity=intensity,
            density_range=(7.0, density_hi),
            dur_range=(0.16, dur_lo),
            rate_jitter_range=(0.1, rate_hi),
            reverse_range=(0.05, reverse_hi),
            distort_range=(0.05, distort_hi),
            position_jitter_range=(0.05, 0.55),
            lpf_range=(14000.0, lpf_lo),
            hpf_range=(30.0, hpf_hi),
            amp_base=0.27,
            progress_curve=rng.random() < 0.4,
        )

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
                "primitives": {
                    "extreme_rates": use_extreme_rates,
                    "heavy_distort": use_heavy_distort,
                    "narrow_band": use_narrow_band,
                    "reverse_bias": use_reverse_bias,
                    "stutter": use_stutter,
                },
            },
        )
