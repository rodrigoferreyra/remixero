"""Intensity → stochastic depth mapping for remix + SuperCollider modulation."""

from __future__ import annotations

from noise_remix.remix.base import intensity_lerp


def rand_depth(intensity: float) -> float:
    """Map intensity to live/random modulation depth in [0, 1].

    This is not a volume control. Higher intensity widens Python jitters and
    deepens seeded SuperCollider stochastic UGens.
    """
    return intensity_lerp(intensity, 0.05, 0.85)


def attach_rand_depth(details: dict, intensity: float) -> dict:
    """Return a copy of details with ``rand_depth`` recorded for the SC layer."""
    out = dict(details)
    out["rand_depth"] = round(rand_depth(intensity), 6)
    return out
