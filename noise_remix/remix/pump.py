"""Pump / transient-emphasis remix strategy — sidechain-style ducking."""

from __future__ import annotations

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.configuration import RemixParameters
from noise_remix.remix.base import intensity_lerp, register
from noise_remix.seed import make_rng


@register
class PumpMode:
    name = "pump"

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

        # Prefer analysis BPM when plausible; else intensity-mapped club tempos.
        bpm = analysis.estimated_bpm
        if bpm is not None and 70.0 <= bpm <= 180.0:
            rate_hz = (bpm / 60.0) * rng.choice([1.0, 2.0])
        else:
            rate_hz = intensity_lerp(intensity, 1.8, 4.5) * rng.uniform(0.92, 1.08)
        rate_hz = max(1.0, min(8.0, rate_hz))

        depth = intensity_lerp(intensity, 0.35, 0.92)
        pulse_width = intensity_lerp(intensity, 0.22, 0.08)  # shorter = harder pump
        transient_boost = intensity_lerp(intensity, 0.15, 0.85)
        drive = intensity_lerp(intensity, 1.0, 2.8)
        hpf = intensity_lerp(intensity, 40.0, 120.0)
        lpf = intensity_lerp(intensity, 14000.0, 6000.0)
        rate = 1.0 + rng.uniform(-0.03, 0.03) * intensity

        return RemixParameters(
            mode=self.name,
            intensity=intensity,
            seed=seed,
            duration=duration,
            sample_rate=analysis.sample_rate,
            channels=analysis.channels,
            details={
                "engine": "pump",
                "pump_rate": round(rate_hz, 6),
                "depth": round(depth, 6),
                "pulse_width": round(pulse_width, 6),
                "transient_boost": round(transient_boost, 6),
                "drive": round(drive, 6),
                "hpf": round(hpf, 3),
                "lpf": round(lpf, 3),
                "playback_rate": round(max(0.85, min(1.15, rate)), 6),
            },
        )
