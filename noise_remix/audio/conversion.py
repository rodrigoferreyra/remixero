"""Audio conversion helpers via FFmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from noise_remix.errors import ConversionError, DependencyError


def find_ffmpeg() -> Path:
    path = shutil.which("ffmpeg")
    if path is None:
        raise DependencyError(
            "ffmpeg was not found on PATH. Install FFmpeg and ensure "
            "ffmpeg is available."
        )
    return Path(path)


def convert_to_wav(
    source: Path,
    destination: Path,
    *,
    sample_rate: int | None = None,
    channels: int | None = None,
    max_duration: float | None = None,
) -> Path:
    """Convert *source* to WAV at *destination* without modifying *source*."""
    ffmpeg = find_ffmpeg()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ConversionError(
            f"Refusing to overwrite existing conversion target: {destination}"
        )

    command = [str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-i", str(source)]
    if max_duration is not None:
        if max_duration <= 0:
            raise ConversionError("max_duration must be positive.")
        command.extend(["-t", f"{max_duration:.6f}"])
    if sample_rate is not None:
        command.extend(["-ar", str(sample_rate)])
    if channels is not None:
        command.extend(["-ac", str(channels)])
    command.extend(["-c:a", "pcm_s16le", str(destination)])

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise DependencyError(f"Failed to run ffmpeg: {exc}") from exc

    if completed.returncode != 0 or not destination.is_file():
        detail = (completed.stderr or completed.stdout or "").strip()
        raise ConversionError(
            f"FFmpeg failed to convert '{source}' to WAV. {detail}"
        )
    return destination
