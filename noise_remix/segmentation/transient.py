"""Transient-based segmentation."""

from __future__ import annotations

from noise_remix.models.analysis import Segment


class TransientSegmenter:
    """Build regions between consecutive onset times."""

    def __init__(self, *, min_duration: float = 0.05, max_duration: float = 2.0) -> None:
        self.min_duration = min_duration
        self.max_duration = max_duration

    def segment(self, transients: list[float], duration: float) -> list[Segment]:
        if duration <= 0:
            return []
        bounds = [0.0, *[t for t in transients if 0.0 < t < duration], duration]
        # Deduplicate near-identical bounds.
        cleaned: list[float] = [bounds[0]]
        for value in bounds[1:]:
            if value - cleaned[-1] >= self.min_duration:
                cleaned.append(value)
        if cleaned[-1] < duration:
            cleaned.append(duration)

        segments: list[Segment] = []
        for start, end in zip(cleaned, cleaned[1:], strict=False):
            if end - start < self.min_duration:
                continue
            cursor = start
            while end - cursor > self.max_duration:
                segments.append(
                    Segment(start=cursor, end=cursor + self.max_duration, kind="transient")
                )
                cursor += self.max_duration
            if end - cursor >= self.min_duration:
                segments.append(Segment(start=cursor, end=end, kind="transient"))
        return segments
