"""Environment and tool discovery models."""

from __future__ import annotations

from pydantic import BaseModel


class EnvironmentInfo(BaseModel):
    """Detected external tool versions."""

    sclang_path: str
    scsynth_path: str
    supercollider_version: str
    ffmpeg_path: str
    ffprobe_path: str
    ffmpeg_version: str | None = None
