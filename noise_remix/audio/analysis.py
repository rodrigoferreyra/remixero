"""Structured audio analysis (does not modify the source file)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from noise_remix.audio.load import load_audio, to_mono
from noise_remix.models.analysis import AmplitudeStats, AudioAnalysis, Segment
from noise_remix.segmentation.fixed import FixedWindowSegmenter
from noise_remix.segmentation.transient import TransientSegmenter


def analyze_audio(path: Path) -> AudioAnalysis:
    """Analyze a local audio file into structured results."""
    samples, sample_rate = load_audio(path)
    channels = int(samples.shape[0])
    n_samples = int(samples.shape[1])
    duration = n_samples / float(sample_rate)
    mono = to_mono(samples)

    amplitude = _amplitude_stats(mono)
    dynamic_range_db, dynamic_label = _dynamic_range(mono)
    flux_curve, hop = _spectral_flux_curve(mono, sample_rate)
    spectral_flux = float(np.mean(flux_curve)) if flux_curve.size else 0.0
    flux_label = _label_unit_interval(_normalize_metric(spectral_flux, scale=0.15))
    centroid = _spectral_centroid(mono, sample_rate)
    transients = _detect_onsets(flux_curve, hop, sample_rate, duration)
    segments = TransientSegmenter().segment(transients, duration)
    if len(segments) < 2:
        segments = FixedWindowSegmenter(window_seconds=0.5).segment([], duration)

    bpm = _estimate_bpm(transients, duration)

    return AudioAnalysis(
        path=str(path.resolve()),
        duration=duration,
        sample_rate=sample_rate,
        channels=channels,
        amplitude=amplitude,
        dynamic_range_db=dynamic_range_db,
        dynamic_range_label=dynamic_label,
        spectral_centroid_hz=centroid,
        spectral_flux=_normalize_metric(spectral_flux, scale=0.15),
        spectral_flux_label=flux_label,
        transients=transients,
        segments=segments,
        estimated_bpm=bpm,
    )


def _amplitude_stats(mono: np.ndarray) -> AmplitudeStats:
    abs_x = np.abs(mono)
    return AmplitudeStats(
        peak=float(np.max(abs_x)) if abs_x.size else 0.0,
        rms=float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0,
        mean_abs=float(np.mean(abs_x)) if abs_x.size else 0.0,
    )


def _dynamic_range(mono: np.ndarray) -> tuple[float, str]:
    """Approximate dynamic range from percentile loudness (dB)."""
    abs_x = np.abs(mono)
    if abs_x.size == 0:
        return 0.0, "low"
    hi = float(np.percentile(abs_x, 99))
    lo = float(np.percentile(abs_x, 10))
    lo = max(lo, 1e-8)
    hi = max(hi, lo)
    dr = 20.0 * float(np.log10(hi / lo))
    if dr < 8:
        label = "low"
    elif dr < 18:
        label = "medium"
    else:
        label = "high"
    return dr, label


def _frame_signal(mono: np.ndarray, frame_size: int, hop: int) -> np.ndarray:
    if mono.size < frame_size:
        padded = np.zeros(frame_size, dtype=np.float32)
        padded[: mono.size] = mono
        return padded[np.newaxis, :]
    n_frames = 1 + (mono.size - frame_size) // hop
    frames = np.stack(
        [mono[i * hop : i * hop + frame_size] for i in range(n_frames)],
        axis=0,
    )
    return frames


def _spectral_flux_curve(mono: np.ndarray, sample_rate: int) -> tuple[np.ndarray, int]:
    frame_size = 1024
    hop = 256
    window = np.hanning(frame_size).astype(np.float32)
    frames = _frame_signal(mono.astype(np.float32), frame_size, hop)
    spectra = np.abs(np.fft.rfft(frames * window, axis=1))
    if spectra.shape[0] < 2:
        return np.zeros(0, dtype=np.float64), hop
    diff = np.diff(spectra, axis=0)
    flux = np.sum(np.maximum(diff, 0.0), axis=1)
    return flux.astype(np.float64), hop


def _spectral_centroid(mono: np.ndarray, sample_rate: int) -> float:
    frame_size = 2048
    if mono.size < frame_size:
        frame = np.zeros(frame_size, dtype=np.float32)
        frame[: mono.size] = mono.astype(np.float32)
    else:
        mid = mono.size // 2
        start = max(0, mid - frame_size // 2)
        frame = mono[start : start + frame_size].astype(np.float32)
        if frame.size < frame_size:
            padded = np.zeros(frame_size, dtype=np.float32)
            padded[: frame.size] = frame
            frame = padded
    windowed = frame * np.hanning(frame_size)
    mag = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(frame_size, d=1.0 / sample_rate)
    denom = float(np.sum(mag))
    if denom <= 1e-12:
        return 0.0
    return float(np.sum(freqs * mag) / denom)


def _detect_onsets(
    flux: np.ndarray,
    hop: int,
    sample_rate: int,
    duration: float,
) -> list[float]:
    if flux.size == 0:
        return []
    median = float(np.median(flux))
    std = float(np.std(flux))
    threshold = median + 1.5 * std
    min_distance = max(1, int(0.05 * sample_rate / hop))  # 50 ms
    peaks: list[int] = []
    for i in range(1, flux.size - 1):
        if flux[i] < threshold:
            continue
        if flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]:
            if peaks and (i - peaks[-1]) < min_distance:
                if flux[i] > flux[peaks[-1]]:
                    peaks[-1] = i
                continue
            peaks.append(i)
    times = [min(duration, (idx * hop) / float(sample_rate)) for idx in peaks]
    return times


def _estimate_bpm(transients: list[float], duration: float) -> float | None:
    """Very rough inter-onset interval estimate; not authoritative."""
    if len(transients) < 4 or duration <= 0:
        return None
    intervals = np.diff(np.asarray(transients, dtype=np.float64))
    intervals = intervals[(intervals > 0.2) & (intervals < 2.0)]
    if intervals.size < 3:
        return None
    median_ioi = float(np.median(intervals))
    if median_ioi <= 0:
        return None
    bpm = 60.0 / median_ioi
    # Fold into a musically common range.
    while bpm < 70:
        bpm *= 2.0
    while bpm > 180:
        bpm /= 2.0
    return round(bpm, 1)


def _normalize_metric(value: float, *, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return float(max(0.0, min(1.0, value / scale)))


def _label_unit_interval(value: float) -> str:
    if value < 0.33:
        return "low"
    if value < 0.66:
        return "medium"
    return "high"
