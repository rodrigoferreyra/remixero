"""Validate AI production plans against engine capabilities."""

from __future__ import annotations

from noise_remix.ai.registry import CAPABILITY_REGISTRY, executable_mode_for
from noise_remix.ai.repair import resolve_layer_reference
from noise_remix.errors import ProductionPlanError
from noise_remix.models.production import ParameterKV, ProductionPlan, ProductionSection
from noise_remix.remix.feedback import MAX_FEEDBACK

ALLOWED_CURVES = {"linear", "step", "exponential"}
ALLOWED_TRANSITIONS = {
    "crossfade",
    "cut",
    "density_ramp",
    "feedback_ramp",
    "layer_in",
    "layer_out",
    "abrupt",
    "gradual",
}


def validate_production_plan(
    plan: ProductionPlan,
    *,
    source_duration: float,
    max_duration: float | None = None,
) -> ProductionPlan:
    """Semantic validation + clamping. Raises ProductionPlanError on hard failures."""
    if source_duration <= 0:
        raise ProductionPlanError("Source duration must be positive.")

    allowed = set(CAPABILITY_REGISTRY)
    primary = plan.global_parameters.primary_mode.strip().lower()
    if primary not in allowed:
        # Soft-repair unknown primary to first layer processor or destroy.
        fallback = plan.layers[0].processor.strip().lower() if plan.layers else "destroy"
        if fallback not in allowed:
            fallback = "destroy"
        primary = fallback

    # Clamp duration to permitted window.
    limit = max_duration if max_duration is not None else source_duration
    if plan.duration_seconds > limit + 1e-6:
        plan.duration_seconds = limit
    if plan.duration_seconds > source_duration + 1e-6:
        # Renderer currently uses source material duration as the audio buffer.
        plan.duration_seconds = min(plan.duration_seconds, source_duration)

    # Normalize layer ids and drop layers with unknown processors.
    cleaned_layers = []
    seen_ids: set[str] = set()
    for layer in plan.layers:
        layer.id = layer.id.strip()
        if not layer.id:
            continue
        processor = layer.processor.strip().lower()
        if processor not in allowed:
            continue
        layer.processor = processor
        if layer.id in seen_ids:
            suffix = 2
            base = layer.id
            while f"{base}_{suffix}" in seen_ids:
                suffix += 1
            layer.id = f"{base}_{suffix}"
        seen_ids.add(layer.id)
        if layer.end is not None and layer.end <= layer.start:
            layer.end = None
        if layer.end is not None and layer.end > plan.duration_seconds + 1e-3:
            layer.end = plan.duration_seconds
        if layer.start > plan.duration_seconds + 1e-3:
            continue
        kept_steps = []
        for step in layer.processing_chain:
            name = step.processor.strip().lower()
            if name not in allowed:
                continue
            step.processor = name
            params = step.parameters_as_dict()
            _clamp_step_parameters(step.processor, params)
            step.parameters = [
                ParameterKV(name=key, value=value) for key, value in params.items()
            ]
            kept_steps.append(step)
        layer.processing_chain = kept_steps
        layer.automation = [
            event for event in layer.automation if event.curve in ALLOWED_CURVES
        ]
        cleaned_layers.append(layer)

    if not cleaned_layers:
        raise ProductionPlanError("Production plan has no executable layers.")
    plan.layers = cleaned_layers
    layer_ids = {layer.id for layer in plan.layers}

    cleaned_sections: list[ProductionSection] = []
    for section in plan.sections:
        if section.end > plan.duration_seconds + 1e-3:
            section.end = plan.duration_seconds
        if section.start > plan.duration_seconds + 1e-3:
            continue
        if section.end <= section.start:
            continue
        resolved: list[str] = []
        for layer_id in section.active_layers:
            mapped = resolve_layer_reference(
                layer_id,
                layer_ids=layer_ids,
                layers=plan.layers,
            )
            if mapped is not None and mapped not in resolved:
                resolved.append(mapped)
            # Unknown refs are dropped instead of failing the whole plan.
        section.active_layers = resolved
        section.automation = [
            event for event in section.automation if event.curve in ALLOWED_CURVES
        ]
        cleaned_sections.append(section)

    if not cleaned_sections:
        cleaned_sections = [
            ProductionSection(
                start=0.0,
                end=plan.duration_seconds,
                name="full",
                energy=0.5,
                active_layers=[layer.id for layer in plan.layers],
            )
        ]
    plan.sections = cleaned_sections

    cleaned_transitions = []
    for transition in plan.transitions:
        if transition.kind not in ALLOWED_TRANSITIONS:
            continue
        if transition.at > plan.duration_seconds + 1e-3:
            continue
        cleaned_transitions.append(transition)
    plan.transitions = cleaned_transitions

    try:
        executable_mode_for(primary)
    except KeyError as exc:
        raise ProductionPlanError(str(exc)) from exc

    plan.global_parameters.primary_mode = primary
    return plan


def _clamp_step_parameters(processor: str, parameters: dict) -> None:
    entry = CAPABILITY_REGISTRY.get(processor, {})
    specs = entry.get("parameters") or {}
    if "feedback" in parameters and processor == "feedback":
        try:
            value = float(parameters["feedback"])
        except (TypeError, ValueError) as exc:
            raise ProductionPlanError("feedback parameter must be numeric") from exc
        if value > MAX_FEEDBACK:
            parameters["feedback"] = MAX_FEEDBACK
        if value < 0:
            parameters["feedback"] = 0.0
    if "intensity" in parameters:
        try:
            value = float(parameters["intensity"])
        except (TypeError, ValueError) as exc:
            raise ProductionPlanError("intensity parameter must be numeric") from exc
        parameters["intensity"] = max(0.0, min(1.0, value))
    for key, spec in specs.items():
        if key not in parameters or not isinstance(spec, dict):
            continue
        if "min" in spec and "max" in spec:
            try:
                value = float(parameters[key])
            except (TypeError, ValueError):
                continue
            parameters[key] = max(float(spec["min"]), min(float(spec["max"]), value))
