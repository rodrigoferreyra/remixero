"""Detect SuperCollider and FFmpeg tooling."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from noise_remix.errors import DependencyError
from noise_remix.models.environment import EnvironmentInfo

_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


@dataclass(frozen=True, order=True)
class _Version:
    major: int
    minor: int
    patch: int = 0

    @classmethod
    def parse(cls, text: str) -> _Version | None:
        match = _VERSION_RE.search(text)
        if match is None:
            return None
        major, minor, patch = match.groups()
        return cls(int(major), int(minor), int(patch or 0))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def discover_environment() -> EnvironmentInfo:
    """Locate FFmpeg/ffprobe and the newest usable SuperCollider install."""
    ffmpeg = _require_which("ffmpeg")
    ffprobe = _require_which("ffprobe")
    sclang, sc_version = _select_sclang()
    scsynth = _resolve_sibling_or_which(sclang, "scsynth")

    return EnvironmentInfo(
        sclang_path=str(sclang),
        scsynth_path=str(scsynth),
        supercollider_version=str(sc_version),
        ffmpeg_path=str(ffmpeg),
        ffprobe_path=str(ffprobe),
        ffmpeg_version=_ffmpeg_version(ffmpeg),
    )


def build_sclang_env(sclang_path: str | Path) -> dict[str, str]:
    """Environment for headless sclang, preferring the same bin dir for scsynth."""
    env = os.environ.copy()
    sc_dir = str(Path(sclang_path).resolve().parent)
    env["PATH"] = sc_dir + os.pathsep + env.get("PATH", "")
    # Avoid Qt GUI init failures in headless/CI environments.
    env.setdefault("QT_QPA_PLATFORM", "minimal")
    return env


def _require_which(name: str) -> Path:
    found = shutil.which(name)
    if found is None:
        raise DependencyError(
            f"{name} was not found on PATH. Install it and ensure it is available."
        )
    return Path(found)


def _select_sclang() -> tuple[Path, _Version]:
    override = os.environ.get("REMIXERO_SCLANG")
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))

    seen: set[Path] = set()
    for raw in _which_all("sclang"):
        path = Path(raw).resolve()
        if path not in seen:
            seen.add(path)
            candidates.append(path)

    # Prefer apt/system install when /usr/local shadows an older build.
    for extra in (Path("/usr/bin/sclang"), Path("/bin/sclang")):
        if extra.exists():
            resolved = extra.resolve()
            if resolved not in seen:
                seen.add(resolved)
                candidates.append(resolved)

    scored: list[tuple[_Version, Path]] = []
    errors: list[str] = []
    for candidate in candidates:
        if not candidate.is_file():
            errors.append(f"{candidate}: not a file")
            continue
        version = _sclang_version(candidate)
        if version is None:
            errors.append(f"{candidate}: could not read version")
            continue
        scored.append((version, candidate))

    if not scored:
        detail = "; ".join(errors) if errors else "no candidates found"
        raise DependencyError(
            "SuperCollider (sclang) was not found or could not be queried. "
            f"Install SuperCollider and ensure sclang is on PATH. ({detail})"
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    version, path = scored[0]
    return path, version


def _which_all(name: str) -> list[str]:
    """Return all PATH matches for *name* (best-effort)."""
    path_env = os.environ.get("PATH", "")
    matches: list[str] = []
    for directory in path_env.split(os.pathsep):
        if not directory:
            continue
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            matches.append(str(candidate))
    return matches


def _resolve_sibling_or_which(sclang: Path, name: str) -> Path:
    sibling = sclang.parent / name
    if sibling.is_file() and os.access(sibling, os.X_OK):
        return sibling
    found = shutil.which(name)
    if found is None:
        raise DependencyError(
            f"{name} was not found next to {sclang} or on PATH."
        )
    return Path(found)


def _sclang_version(sclang: Path) -> _Version | None:
    try:
        completed = subprocess.run(
            [str(sclang), "-v"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
            env=build_sclang_env(sclang),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (completed.stdout or "") + "\n" + (completed.stderr or "")
    return _Version.parse(text)


def _ffmpeg_version(ffmpeg: Path) -> str | None:
    try:
        completed = subprocess.run(
            [str(ffmpeg), "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    first = (completed.stdout or "").splitlines()[:1]
    if not first:
        return None
    match = _VERSION_RE.search(first[0])
    return match.group(0) if match else first[0].strip()
