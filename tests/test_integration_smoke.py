"""Integration tests requiring SuperCollider and FFmpeg."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from noise_remix.cli.commands import app
from noise_remix.supercollider.environment import discover_environment

FIXTURE = Path(__file__).parent / "fixtures" / "tone_1s.wav"
runner = CliRunner()


def _tools_available() -> bool:
    try:
        discover_environment()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.integration


@pytest.mark.skipif(not _tools_available(), reason="SuperCollider/FFmpeg unavailable")
def test_smoke_render_end_to_end(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    result = runner.invoke(
        app,
        [
            str(FIXTURE),
            "--mode",
            "smoke",
            "--output",
            str(out_dir),
            "--duration",
            "0.5",
            "--keep-patch",
            "--seed",
            "1",
            "--verbose",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    wavs = list(out_dir.glob("*-smoke-*.wav"))
    scds = list(out_dir.glob("*-smoke-*.scd"))
    jsons = list(out_dir.glob("*-smoke-*.json"))
    assert len(wavs) == 1
    assert len(scds) == 1
    assert len(jsons) == 1
    assert wavs[0].stat().st_size > 1000


@pytest.mark.skipif(not _tools_available(), reason="SuperCollider/FFmpeg unavailable")
def test_granular_render_end_to_end(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    result = runner.invoke(
        app,
        [
            str(FIXTURE),
            "--mode",
            "granular",
            "--intensity",
            "0.8",
            "--output",
            str(out_dir),
            "--duration",
            "0.8",
            "--seed",
            "42",
            "--keep-patch",
            "--keep-analysis",
            "--variations",
            "2",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    wavs = sorted(out_dir.glob("*-granular-*.wav"))
    jsons = sorted(out_dir.glob("*-granular-*.json"))
    assert len(wavs) == 2
    assert len(jsons) == 2
    meta = json.loads(jsons[0].read_text(encoding="utf-8"))
    assert meta["mode"] == "granular"
    assert meta["seed"] != json.loads(jsons[1].read_text(encoding="utf-8"))["seed"]
    assert meta["source_hash"]
    assert "remixero_grain" in list(out_dir.glob("*-granular-*.scd"))[0].read_text(
        encoding="utf-8"
    )
    analysis_files = list(out_dir.glob("*analysis*.json"))
    assert analysis_files


@pytest.mark.skipif(not _tools_available(), reason="SuperCollider/FFmpeg unavailable")
def test_additional_modes_render(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    for mode_name in ("destroy", "feedback", "collapse", "random"):
        result = runner.invoke(
            app,
            [
                str(FIXTURE),
                "--mode",
                mode_name,
                "--intensity",
                "0.75",
                "--output",
                str(out_dir),
                "--duration",
                "0.6",
                "--seed",
                "7",
                "--keep-patch",
            ],
        )
        assert result.exit_code == 0, f"{mode_name}: {result.stdout}\n{result.stderr}"
        wavs = list(out_dir.glob(f"*-{mode_name}-*.wav"))
        assert wavs, mode_name
        assert wavs[0].stat().st_size > 1000
