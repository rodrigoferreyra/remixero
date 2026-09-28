"""Propose arrangement section bounds from local audio analysis."""

from __future__ import annotations

from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.production import ProductionPlan, ProductionSection


def propose_section_bounds(
    analysis: AudioAnalysis,
    *,
    energy: str = "medium",
) -> list[dict[str, float | str]]:
    """Build build/drop/breakdown/outro-style bounds from transient density.

    Returns dicts with name/start/end/energy suitable for ProductionSection.
    """
    duration = analysis.duration
    if duration <= 0:
        return []

    # Transient density in fixed hops.
    hop = max(0.25, min(1.0, duration / 16.0))
    bins = max(4, int(duration / hop))
    densities = [0.0] * bins
    for transient in analysis.transients:
        if 0.0 <= transient < duration:
            index = min(bins - 1, int(transient / hop))
            densities[index] += 1.0
    # Smooth.
    smooth = []
    for index, value in enumerate(densities):
        left = densities[index - 1] if index else value
        right = densities[index + 1] if index + 1 < bins else value
        smooth.append((left + value + right) / 3.0)
    peak_index = max(range(bins), key=lambda i: smooth[i])
    peak_t = (peak_index + 0.5) * hop

    if duration < 8.0 or energy == "low":
        # Short / calm: intro → body → outro with guaranteed positive spans.
        a = duration * (0.25 if duration >= 1.0 else 0.33)
        b = duration * (0.7 if duration >= 1.0 else 0.66)
        a = min(max(0.05, a), duration - 0.1)
        b = min(max(a + 0.05, b), duration - 0.05)
        return [
            {"name": "intro", "start": 0.0, "end": a, "energy": 0.35},
            {
                "name": "body",
                "start": a,
                "end": b,
                "energy": 0.55 if energy != "high" else 0.75,
            },
            {"name": "outro", "start": b, "end": duration, "energy": 0.3},
        ]

    # Longer form: build → drop → break → peak/outro
    build_end = max(duration * 0.18, min(peak_t * 0.7, duration * 0.4))
    drop_end = max(build_end + duration * 0.15, min(peak_t + duration * 0.12, duration * 0.7))
    break_end = max(drop_end + duration * 0.1, duration * 0.85)
    # Ensure strictly increasing bounds.
    build_end = min(build_end, duration * 0.35)
    drop_end = min(max(build_end + 0.2, drop_end), duration * 0.7)
    break_end = min(max(drop_end + 0.2, break_end), duration - 0.05)
    if energy == "high":
        return [
            {"name": "build", "start": 0.0, "end": build_end, "energy": 0.45},
            {"name": "drop", "start": build_end, "end": drop_end, "energy": 0.95},
            {"name": "break", "start": drop_end, "end": break_end, "energy": 0.4},
            {"name": "finale", "start": break_end, "end": duration, "energy": 0.9},
        ]
    return [
        {"name": "intro", "start": 0.0, "end": build_end, "energy": 0.35},
        {"name": "rise", "start": build_end, "end": drop_end, "energy": 0.65},
        {"name": "peak", "start": drop_end, "end": break_end, "energy": 0.8},
        {"name": "outro", "start": break_end, "end": duration, "energy": 0.35},
    ]


def apply_analysis_arrangement(
    plan: ProductionPlan,
    analysis: AudioAnalysis,
    *,
    energy: str = "medium",
) -> ProductionPlan:
    """Replace section timeline with analysis-proposed bounds; keep layer roles.

    Layer activity is reassigned by ranking layers by intensity/aggressiveness so
    quieter processors favor early sections and aggressive ones favor peaks.
    """
    bounds = propose_section_bounds(analysis, energy=energy)
    if len(bounds) < 2:
        return plan

    ranked = sorted(
        plan.layers,
        key=lambda layer: (
            _aggression(layer.processor),
            layer.intensity,
            layer.volume,
        ),
    )
    soft = [layer.id for layer in ranked[: max(1, len(ranked) // 2)]]
    hard = [layer.id for layer in ranked[max(1, len(ranked) // 2) :]] or soft
    all_ids = [layer.id for layer in plan.layers]

    new_sections: list[ProductionSection] = []
    for bound in bounds:
        name = str(bound["name"])
        section_energy = float(bound["energy"])
        if section_energy >= 0.75:
            active = list(dict.fromkeys(hard + soft[-1:]))
        elif section_energy <= 0.4:
            active = list(soft) or all_ids[:1]
        else:
            active = list(dict.fromkeys(soft + hard[:1]))
        new_sections.append(
            ProductionSection(
                start=float(bound["start"]),
                end=float(bound["end"]),
                name=name,
                energy=section_energy,
                description=f"analysis-arranged:{name}",
                active_layers=active,
            )
        )
    plan.sections = new_sections
    # Drop old transitions; timing/crossfade pass will recreate them.
    plan.transitions = []
    return plan


def _aggression(processor: str) -> float:
    order = {
        "passthrough": 0.0,
        "granular": 0.25,
        "pitch_warp": 0.35,
        "comb": 0.45,
        "stutter": 0.7,
        "pump": 0.75,
        "ring_mod": 0.8,
        "feedback": 0.85,
        "random": 0.9,
        "collapse": 0.92,
        "destroy": 1.0,
    }
    return order.get(processor, 0.5)
