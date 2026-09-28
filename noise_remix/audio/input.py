"""Input audio validation."""

from __future__ import annotations

from pathlib import Path

from noise_remix.audio.probe import probe_audio
from noise_remix.errors import InputError
from noise_remix.models.analysis import AudioProbe

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg"}


def validate_input(path: Path) -> AudioProbe:
    """Validate that *path* is a readable supported audio file and probe it."""
    if not path.exists():
        raise InputError(f"Input file not found: {path}")
    if not path.is_file():
        raise InputError(f"Input path is not a file: {path}")
    if not path.suffix.lower() in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise InputError(
            f"Unsupported audio format '{path.suffix}'. Supported: {supported}"
        )
    try:
        path.open("rb").close()
    except OSError as exc:
        raise InputError(f"Input file is not readable: {path}") from exc

    probe = probe_audio(path)
    return probe
