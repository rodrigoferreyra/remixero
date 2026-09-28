"""Invoke SuperCollider for non-realtime rendering."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from noise_remix.audio.probe import probe_audio
from noise_remix.errors import RenderError
from noise_remix.models.environment import EnvironmentInfo
from noise_remix.supercollider.environment import build_sclang_env


def render_patch(
    *,
    patch_path: Path,
    output_wav: Path,
    env_info: EnvironmentInfo,
    timeout_seconds: float = 120.0,
) -> Path:
    """Run *patch_path* with sclang and verify *output_wav* exists and is audio."""
    if output_wav.exists():
        raise RenderError(
            f"Refusing to overwrite existing render output: {output_wav}"
        )

    command = [
        env_info.sclang_path,
        "-D",
        str(patch_path.resolve()),
    ]
    env = build_sclang_env(env_info.sclang_path)

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError(
            f"SuperCollider timed out after {timeout_seconds:.0f}s while rendering."
        ) from exc
    except OSError as exc:
        raise RenderError(f"Failed to launch sclang: {exc}") from exc

    # Give the filesystem a brief moment if the process just flushed.
    deadline = time.time() + 2.0
    while time.time() < deadline and not output_wav.exists():
        time.sleep(0.05)

    if completed.returncode != 0:
        detail = _format_sc_output(completed.stdout, completed.stderr)
        raise RenderError(
            "SuperCollider exited with an error and did not complete rendering.\n"
            f"{detail}"
        )

    if not output_wav.is_file():
        detail = _format_sc_output(completed.stdout, completed.stderr)
        raise RenderError(
            f"SuperCollider finished but output was not created: {output_wav}\n"
            f"{detail}"
        )

    try:
        probe_audio(output_wav)
    except Exception as exc:  # noqa: BLE001 - surface as render failure
        raise RenderError(
            f"Rendered file exists but is not valid audio: {output_wav}"
        ) from exc

    return output_wav


def _format_sc_output(stdout: str | None, stderr: str | None) -> str:
    parts: list[str] = []
    if stdout and stdout.strip():
        parts.append("stdout:\n" + stdout.strip())
    if stderr and stderr.strip():
        parts.append("stderr:\n" + stderr.strip())
    return "\n".join(parts) if parts else "(no SuperCollider output captured)"
