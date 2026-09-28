"""Analysis-related data models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AudioProbe(BaseModel):
    """Basic media probe of a source audio file."""

    path: str
    format_name: str
    codec_name: str | None = None
    duration: float = Field(gt=0)
    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    bit_rate: int | None = None


class AmplitudeStats(BaseModel):
    peak: float = Field(ge=0.0)
    rms: float = Field(ge=0.0)
    mean_abs: float = Field(ge=0.0)


class Segment(BaseModel):
    start: float = Field(ge=0.0)
    end: float = Field(gt=0.0)
    kind: str = "transient"

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


class AudioAnalysis(BaseModel):
    """Structured analysis results (source file is never modified)."""

    path: str
    duration: float = Field(gt=0)
    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    amplitude: AmplitudeStats
    dynamic_range_db: float
    dynamic_range_label: Literal["low", "medium", "high"]
    spectral_centroid_hz: float = Field(ge=0.0)
    spectral_flux: float = Field(ge=0.0)
    spectral_flux_label: Literal["low", "medium", "high"]
    transients: list[float] = Field(default_factory=list)
    segments: list[Segment] = Field(default_factory=list)
    estimated_bpm: float | None = Field(
        default=None,
        description="Approximate only; never treat as authoritative.",
    )
