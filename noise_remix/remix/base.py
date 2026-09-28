"""Remix strategy interfaces and registry."""

from __future__ import annotations

from typing import Protocol

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.configuration import RemixParameters


class RemixMode(Protocol):
    name: str

    def generate(
        self,
        *,
        analysis: AudioAnalysis,
        intensity: float,
        seed: int,
        duration: float,
    ) -> RemixParameters:
        """Produce structured remix parameters (not SuperCollider code)."""


_REGISTRY: dict[str, RemixMode] = {}


def register(mode_cls: type) -> type:
    """Register a remix mode class by instantiating it once."""
    instance = mode_cls()
    _REGISTRY[instance.name] = instance
    return mode_cls


def get_mode(name: str) -> RemixMode:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(f"Unknown remix mode '{name}'. Available: {available}") from exc


def available_modes() -> list[str]:
    return sorted(_REGISTRY)


def intensity_lerp(intensity: float, low: float, high: float) -> float:
    intensity = max(0.0, min(1.0, intensity))
    return low + (high - low) * intensity
