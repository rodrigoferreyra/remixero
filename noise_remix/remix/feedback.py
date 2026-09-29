"""Feedback remix strategy — bounded delay/feedback processing."""

from __future__ import annotations

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.configuration import RemixParameters
from noise_remix.remix.base import intensity_lerp, register
from noise_remix.remix.chaos import attach_rand_depth, rand_depth
from noise_remix.seed import make_rng

# Hard ceiling — never generate uncontrolled runaway feedback.
MAX_FEEDBACK = 0.82


@register
class FeedbackMode:
    name = "feedback"

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

        delay_spread = 0.15 + 0.2 * depth
        delay_time = intensity_lerp(intensity, 0.08, 0.35) * rng.uniform(
            1.0 - delay_spread, 1.0 + delay_spread
        )
        delay_time = max(0.02, min(0.45, delay_time))
        feedback = intensity_lerp(intensity, 0.2, MAX_FEEDBACK) * rng.uniform(0.88, 1.0)
        feedback = max(0.05, min(MAX_FEEDBACK, feedback))
        drive = intensity_lerp(intensity, 1.0, 4.5) * rng.uniform(0.92, 1.08)
        lpf = intensity_lerp(intensity, 10000.0, 1800.0)
        hpf = intensity_lerp(intensity, 40.0, 300.0)
        pitch_dispersion = intensity_lerp(intensity, 0.0, 0.15 * (1.0 + 0.3 * depth))
        rate = 1.0 + rng.uniform(-0.05 - 0.08 * depth, 0.05 + 0.08 * depth) * intensity
        rate = max(0.85, min(1.15, rate))

        return RemixParameters(
            mode=self.name,
            intensity=intensity,
            seed=seed,
            duration=duration,
            sample_rate=analysis.sample_rate,
            channels=analysis.channels,
            details=attach_rand_depth(
                {
                    "engine": "feedback",
                    "delay_time": round(delay_time, 6),
                    "feedback": round(feedback, 6),
                    "max_feedback": MAX_FEEDBACK,
                    "drive": round(drive, 6),
                    "lpf": round(lpf, 3),
                    "hpf": round(hpf, 3),
                    "pitch_dispersion": round(pitch_dispersion, 6),
                    "playback_rate": round(rate, 6),
                },
                intensity,
            ),
        )
