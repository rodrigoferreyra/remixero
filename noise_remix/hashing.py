"""Source file hashing for reproducibility metadata."""

from __future__ import annotations

import hashlib
from pathlib import Path


def hash_file(path: Path, *, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
