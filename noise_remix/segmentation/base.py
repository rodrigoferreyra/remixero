"""Segmentation interfaces."""

from __future__ import annotations

from typing import Protocol

from noise_remix.models.analysis import Segment


class Segmenter(Protocol):
    """Reusable segmentation strategy."""

    def segment(self, transients: list[float], duration: float) -> list[Segment]:
        """Return usable source regions within [0, duration]."""
