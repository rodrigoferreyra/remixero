"""Fixed-duration window segmentation."""

from __future__ import annotations

from noise_remix.models.analysis import Segment


class FixedWindowSegmenter:
    def __init__(self, *, window_seconds: float = 0.5) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.window_seconds = window_seconds

    def segment(self, transients: list[float], duration: float) -> list[Segment]:
        del transients  # unused by design
        if duration <= 0:
            return []
        segments: list[Segment] = []
        start = 0.0
        while start < duration:
            end = min(duration, start + self.window_seconds)
            if end - start >= 0.01:
                segments.append(Segment(start=start, end=end, kind="fixed"))
            start = end
        return segments
