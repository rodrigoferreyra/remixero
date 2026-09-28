"""Load audio into a consistent float representation for analysis."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from noise_remix.errors import InputError


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    """Load audio as float32 shape (channels, samples), preserving channel count."""
    try:
        data, sample_rate = sf.read(str(path), always_2d=True, dtype="float32")
    except Exception as exc:  # noqa: BLE001 - soundfile raises varied errors
        raise InputError(f"Could not load audio for analysis: {path}") from exc

    if data.size == 0:
        raise InputError(f"Audio file contains no samples: {path}")

    # soundfile returns (frames, channels); convert to (channels, samples)
    samples = np.ascontiguousarray(data.T)
    return samples, int(sample_rate)


def to_mono(samples: np.ndarray) -> np.ndarray:
    """Mix down to mono for analysis helpers that expect 1-D audio."""
    if samples.ndim != 2:
        raise ValueError("samples must have shape (channels, samples)")
    if samples.shape[0] == 1:
        return samples[0]
    return np.mean(samples, axis=0)
