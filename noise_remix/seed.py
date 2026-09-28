"""Deterministic seed helpers."""

from __future__ import annotations

import secrets
from random import Random

from noise_remix.errors import InputError


def resolve_seed(value: str | int | None) -> int:
    """Resolve CLI seed value into a concrete non-negative integer."""
    if value is None or value == "random":
        return secrets.randbelow(2**31 - 1) or 1
    if isinstance(value, int):
        if value < 0:
            raise InputError("--seed must be non-negative or 'random'.")
        return value
    text = str(value).strip().lower()
    if text == "random":
        return secrets.randbelow(2**31 - 1) or 1
    try:
        parsed = int(text, 10)
    except ValueError as exc:
        raise InputError("--seed must be an integer or 'random'.") from exc
    if parsed < 0:
        raise InputError("--seed must be non-negative or 'random'.")
    return parsed


def variation_seed(base_seed: int, variation_index: int) -> int:
    """Derive a distinct deterministic seed for each variation."""
    rng = Random((base_seed + 1) * 1_000_003 + variation_index)
    return rng.randint(1, 2**31 - 1)


def make_rng(seed: int) -> Random:
    return Random(seed)
