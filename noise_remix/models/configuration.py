"""Remix configuration and metadata models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RemixParameters(BaseModel):
    """Structured parameters produced by a remix strategy."""

    mode: str
    intensity: float = Field(ge=0.0, le=1.0)
    seed: int
    duration: float = Field(gt=0.0)
    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    details: dict[str, Any] = Field(default_factory=dict)


class RenderMetadata(BaseModel):
    """Reproducibility metadata written alongside each render."""

    source: str
    source_hash: str
    mode: str
    intensity: float
    seed: int
    duration: float
    created_at: str
    software_version: str
    supercollider_version: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    analysis_summary: dict[str, Any] = Field(default_factory=dict)
