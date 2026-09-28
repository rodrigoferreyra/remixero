"""Machine-readable DSP capability registry for AI orchestration."""

from __future__ import annotations

from typing import Any

# Processors currently executable by the Remixero engine.
# AI providers may only request processors listed here.
CAPABILITY_REGISTRY: dict[str, dict[str, Any]] = {
    "granular": {
        "description": (
            "Fragment source audio into overlapping grains with rate/pan/reverse variation. "
            "Good for texture beds and rhythmic clouds."
        ),
        "executable_mode": "granular",
        "parameters": {
            "intensity": {"min": 0.0, "max": 1.0, "default": 0.5},
            "grain_size": {"min": 0.025, "max": 0.12, "note": "mapped from intensity"},
            "density": {"min": 8.0, "max": 45.0, "note": "mapped from intensity"},
            "reverse_probability": {"min": 0.0, "max": 0.45},
        },
    },
    "destroy": {
        "description": (
            "Aggressive fragmentation with extreme rates, distortion, and filtering."
        ),
        "executable_mode": "destroy",
        "parameters": {
            "intensity": {"min": 0.0, "max": 1.0, "default": 0.5},
            "distort": {"min": 0.15, "max": 0.95},
            "rate_jitter": {"min": 0.15, "max": 1.8},
        },
    },
    "collapse": {
        "description": (
            "Progressive densification and degradation from recognizable toward crushed texture."
        ),
        "executable_mode": "collapse",
        "parameters": {
            "intensity": {"min": 0.0, "max": 1.0, "default": 0.5},
            "feedback_amount": {"min": 0.05, "max": 0.55},
        },
    },
    "feedback": {
        "description": (
            "Bounded delay/feedback loop with filtering, soft clipping, pitch smear, and hard limiting."
        ),
        "executable_mode": "feedback",
        "parameters": {
            "intensity": {"min": 0.0, "max": 1.0, "default": 0.5},
            "feedback": {"min": 0.05, "max": 0.82, "hard_max": 0.82},
            "delay_time": {"min": 0.02, "max": 0.45},
            "drive": {"min": 1.0, "max": 4.5},
        },
    },
    "comb": {
        "description": (
            "Comb-filter / resonator coloration over looping source playback. "
            "Creates metallic ringing and hollow tunnels."
        ),
        "executable_mode": "comb",
        "parameters": {
            "intensity": {"min": 0.0, "max": 1.0, "default": 0.5},
            "delay_time": {"min": 0.005, "max": 0.2},
            "decay": {"min": 0.2, "max": 6.0},
            "wet": {"min": 0.1, "max": 0.95},
        },
    },
    "ring_mod": {
        "description": (
            "Ring modulation of the source against a carrier oscillator for harsh, "
            "inharmonic, metallic spectra."
        ),
        "executable_mode": "ring_mod",
        "parameters": {
            "intensity": {"min": 0.0, "max": 1.0, "default": 0.5},
            "mod_freq": {"min": 20.0, "max": 2000.0},
            "depth": {"min": 0.1, "max": 1.0},
            "drive": {"min": 1.0, "max": 3.5},
        },
    },
    "pitch_warp": {
        "description": (
            "Continuous pitch shifting and playback-rate warping with dispersion. "
            "Useful for drones, drops, and unrecognizable stretches."
        ),
        "executable_mode": "pitch_warp",
        "parameters": {
            "intensity": {"min": 0.0, "max": 1.0, "default": 0.5},
            "pitch_ratio": {"min": 0.25, "max": 2.5},
            "pitch_dispersion": {"min": 0.0, "max": 0.2},
            "wet": {"min": 0.2, "max": 1.0},
        },
    },
    "stutter": {
        "description": (
            "Rapid locked buffer slices / freezes with occasional jumps — glitch stutter."
        ),
        "executable_mode": "stutter",
        "parameters": {
            "intensity": {"min": 0.0, "max": 1.0, "default": 0.5},
            "density": {"min": 6.0, "max": 28.0, "note": "mapped from intensity"},
            "hold_probability": {"min": 0.2, "max": 0.95},
        },
    },
    "pump": {
        "description": (
            "Sidechain-style pumping ducking synced to tempo/transients with transient boost. "
            "Useful for hardcore/EDM pressure without inventing drums."
        ),
        "executable_mode": "pump",
        "parameters": {
            "intensity": {"min": 0.0, "max": 1.0, "default": 0.5},
            "pump_rate": {"min": 1.0, "max": 8.0},
            "depth": {"min": 0.2, "max": 0.95},
            "transient_boost": {"min": 0.0, "max": 1.0},
            "drive": {"min": 1.0, "max": 2.8},
        },
    },
    "random": {
        "description": (
            "Seeded combination of fragmentation primitives (rates, stutter, band-limiting)."
        ),
        "executable_mode": "random",
        "parameters": {
            "intensity": {"min": 0.0, "max": 1.0, "default": 0.5},
        },
    },
    "passthrough": {
        "description": "Nearly dry source with limiter (reference / sparse bed layer).",
        "executable_mode": "smoke",
        "parameters": {
            "intensity": {"min": 0.0, "max": 1.0, "default": 0.0},
        },
    },
}


def registry_processor_names() -> list[str]:
    return sorted(CAPABILITY_REGISTRY)


def executable_mode_for(processor: str) -> str:
    entry = CAPABILITY_REGISTRY.get(processor)
    if entry is None:
        raise KeyError(processor)
    return str(entry["executable_mode"])


def registry_for_prompt() -> dict[str, Any]:
    """Compact registry suitable for AI context."""
    return {
        name: {
            "description": data["description"],
            "parameters": data["parameters"],
        }
        for name, data in CAPABILITY_REGISTRY.items()
    }
