"""Unit tests for CLI validation and helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from noise_remix.audio.analysis import analyze_audio
from noise_remix.audio.input import validate_input
from noise_remix.cli.commands import _resolve_analysis_duration, app
from noise_remix.errors import InputError
from noise_remix.hashing import hash_file
from noise_remix.output.manager import allocate_output_paths
from noise_remix.remix import get_mode
from noise_remix.seed import resolve_seed, variation_seed
from noise_remix.supercollider.generator import escape_sc_string, generate_patch

FIXTURE = Path(__file__).parent / "fixtures" / "tone_1s.wav"
runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "INPUT" in result.stdout
    assert "--mode" in result.stdout
    assert "--intensity" in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "remixero 0.1.0" in result.stdout


def test_missing_input() -> None:
    result = runner.invoke(app, ["does-not-exist.wav"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower() or "not found" in result.stderr.lower()


def test_unsupported_format(tmp_path: Path) -> None:
    bad = tmp_path / "song.txt"
    bad.write_text("nope", encoding="utf-8")
    with pytest.raises(InputError, match="Unsupported"):
        validate_input(bad)


def test_validate_fixture() -> None:
    probe = validate_input(FIXTURE)
    assert probe.duration > 0.9
    assert probe.sample_rate == 44100
    assert probe.channels == 2


def test_resolve_duration_smoke_cap() -> None:
    assert _resolve_analysis_duration(120.0, None, mode="smoke") == 5.0
    assert _resolve_analysis_duration(2.0, None, mode="granular") == 2.0


def test_resolve_duration_explicit() -> None:
    assert _resolve_analysis_duration(10.0, 3.0, mode="granular") == 3.0
    with pytest.raises(InputError):
        _resolve_analysis_duration(10.0, 0.0, mode="granular")


def test_allocate_output_paths_no_overwrite(tmp_path: Path) -> None:
    first, meta1, _ = allocate_output_paths(
        output_dir=tmp_path, source_stem="song", mode="granular"
    )
    first.write_bytes(b"x")
    meta1.write_text("{}", encoding="utf-8")
    second, meta2, _ = allocate_output_paths(
        output_dir=tmp_path, source_stem="song", mode="granular"
    )
    assert first.name.endswith("-001.wav")
    assert second.name.endswith("-002.wav")
    assert meta2.name.endswith("-002.json")


def test_escape_sc_string() -> None:
    assert escape_sc_string(r'a\b"c') == r'a\\b\"c'


def test_analyze_fixture() -> None:
    analysis = analyze_audio(FIXTURE)
    assert analysis.duration > 0.9
    assert analysis.sample_rate == 44100
    assert analysis.channels == 2
    assert analysis.amplitude.peak > 0
    assert len(analysis.segments) >= 1
    assert 0.0 <= analysis.spectral_flux <= 1.0


def test_seed_resolution_and_variations() -> None:
    assert resolve_seed(42) == 42
    assert resolve_seed("99") == 99
    a = variation_seed(1, 0)
    b = variation_seed(1, 1)
    assert a != b
    assert variation_seed(1, 0) == a


def test_source_hash_stable() -> None:
    assert hash_file(FIXTURE) == hash_file(FIXTURE)


def test_granular_deterministic_params() -> None:
    analysis = analyze_audio(FIXTURE)
    mode = get_mode("granular")
    a = mode.generate(analysis=analysis, intensity=0.7, seed=123, duration=1.0)
    b = mode.generate(analysis=analysis, intensity=0.7, seed=123, duration=1.0)
    assert a.details["grains"] == b.details["grains"]
    soft = mode.generate(analysis=analysis, intensity=0.1, seed=123, duration=1.0)
    hard = mode.generate(analysis=analysis, intensity=0.9, seed=123, duration=1.0)
    assert soft.details["density"] < hard.details["density"]
    assert soft.details["grain_duration"] > hard.details["grain_duration"]


def test_generate_granular_patch_contains_grains(tmp_path: Path) -> None:
    analysis = analyze_audio(FIXTURE)
    params = get_mode("granular").generate(
        analysis=analysis, intensity=0.5, seed=7, duration=0.5
    )
    text = generate_patch(
        params=params,
        input_wav=tmp_path / "in.wav",
        output_wav=tmp_path / "out.wav",
    )
    assert "remixero_grain" in text
    assert "Limiter.ar" in text
    assert "/b_allocRead" in text
    assert "0.exit" in text


def test_invalid_intensity_cli() -> None:
    result = runner.invoke(app, [str(FIXTURE), "--intensity", "1.5"])
    assert result.exit_code == 1
    assert "intensity" in result.stdout.lower()
