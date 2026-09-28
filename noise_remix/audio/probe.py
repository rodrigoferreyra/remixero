"""Probe audio files with ffprobe."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from noise_remix.errors import DependencyError, InputError
from noise_remix.models.analysis import AudioProbe


def find_ffprobe() -> Path:
    path = shutil.which("ffprobe")
    if path is None:
        raise DependencyError(
            "ffprobe was not found on PATH. Install FFmpeg and ensure "
            "ffprobe is available."
        )
    return Path(path)


def probe_audio(path: Path) -> AudioProbe:
    """Return structured media information for *path* using ffprobe."""
    ffprobe = find_ffprobe()
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path.resolve()),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise DependencyError(f"Failed to run ffprobe: {exc}") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise InputError(
            f"Could not inspect audio file '{path}'. "
            f"It may be corrupt or unsupported. {detail}"
        )

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise InputError(f"ffprobe returned invalid JSON for '{path}'.") from exc

    streams = payload.get("streams") or []
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    if not audio_streams:
        raise InputError(f"No audio stream found in '{path}'.")

    stream = audio_streams[0]
    fmt = payload.get("format") or {}

    duration = _to_float(stream.get("duration")) or _to_float(fmt.get("duration"))
    sample_rate = _to_int(stream.get("sample_rate"))
    channels = _to_int(stream.get("channels"))

    if duration is None or duration <= 0:
        raise InputError(f"Could not determine a positive duration for '{path}'.")
    if sample_rate is None or sample_rate <= 0:
        raise InputError(f"Could not determine sample rate for '{path}'.")
    if channels is None or channels <= 0:
        raise InputError(f"Could not determine channel count for '{path}'.")

    return AudioProbe(
        path=str(path.resolve()),
        format_name=str(fmt.get("format_name") or path.suffix.lstrip(".")),
        codec_name=stream.get("codec_name"),
        duration=duration,
        sample_rate=sample_rate,
        channels=channels,
        bit_rate=_to_int(fmt.get("bit_rate") or stream.get("bit_rate")),
    )


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None
