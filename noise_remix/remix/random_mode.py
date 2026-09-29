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
        # Mid/high intensity leans harder into extreme branches.
        use_extreme_rates = rng.random() < intensity_lerp(intensity, 0.28, 0.95)
        use_heavy_distort = rng.random() < intensity_lerp(intensity, 0.22, 0.92)
        use_narrow_band = rng.random() < intensity_lerp(intensity, 0.15, 0.8)
        use_reverse_bias = rng.random() < intensity_lerp(intensity, 0.28, 0.9)
        use_stutter = rng.random() < intensity_lerp(intensity, 0.32, 0.95)

        density_hi = 60.0 if use_stutter else 34.0
        dur_lo = 0.015 if use_stutter else 0.035
        rate_hi = 2.6 if use_extreme_rates else 1.0
        distort_hi = 0.95 if use_heavy_distort else 0.5
        reverse_hi = 0.8 if use_reverse_bias else 0.4
        lpf_lo = 1000.0 if use_narrow_band else 3800.0
        hpf_hi = 1400.0 if use_narrow_band else 450.0

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
            position_jitter_range=(0.05, 0.7),
            lpf_range=(14000.0, lpf_lo),
            hpf_range=(30.0, hpf_hi),
            amp_base=0.27,
            progress_curve=rng.random() < intensity_lerp(intensity, 0.35, 0.65),
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
