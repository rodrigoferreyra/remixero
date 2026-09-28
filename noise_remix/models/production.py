"""Structured production plan models for AI orchestration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class AutomationEvent(BaseModel):
    """Parameter change over time within a section or layer."""

    target: str = Field(description="Parameter name, e.g. density, feedback, volume")
    time: float = Field(ge=0.0)
    value: float
    curve: str = Field(
        default="linear",
        description="linear | step | exponential",
    )


class ParameterKV(BaseModel):
    """Named parameter entry — avoids open dict schemas unsupported on Gemini Developer API."""

    name: str
    value: float | int | bool | str


class ProcessingStep(BaseModel):
    processor: str
    parameters: list[ParameterKV] = Field(default_factory=list)

    @field_validator("parameters", mode="before")
    @classmethod
    def _coerce_parameters(cls, value: object) -> object:
        # Accept legacy/open dict payloads and normalize to ParameterKV list.
        if isinstance(value, dict):
            return [{"name": str(k), "value": v} for k, v in value.items()]
        return value

    def parameters_as_dict(self) -> dict[str, float | int | bool | str]:
        return {item.name: item.value for item in self.parameters}


class AudioLayer(BaseModel):
    id: str
    processor: str = Field(description="DSP primitive from the capability registry")
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    volume: float = Field(default=1.0, ge=0.0, le=2.0)
    pan: float = Field(default=0.0, ge=-1.0, le=1.0)
    start: float = Field(default=0.0, ge=0.0)
    end: float | None = Field(default=None, ge=0.0)
    processing_chain: list[ProcessingStep] = Field(default_factory=list)
    automation: list[AutomationEvent] = Field(default_factory=list)
    notes: str = ""


class ProductionSection(BaseModel):
    start: float = Field(ge=0.0)
    end: float = Field(gt=0.0)
    name: str
    energy: float = Field(default=0.5, ge=0.0, le=1.0)
    description: str = ""
    active_layers: list[str] = Field(default_factory=list)
    automation: list[AutomationEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_span(self) -> ProductionSection:
        if self.end <= self.start:
            raise ValueError("section end must be greater than start")
        return self


class Transition(BaseModel):
    at: float = Field(ge=0.0)
    kind: str = Field(
        default="crossfade",
        description="crossfade | cut | density_ramp | feedback_ramp | layer_in | layer_out",
    )
    description: str = ""
    duration: float = Field(default=0.0, ge=0.0)


class GlobalParameters(BaseModel):
    overall_intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    primary_mode: str = Field(
        description="Primary processor (metadata / fallback if no layers render)"
    )
    source_preservation: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="1=keep recognizable, 0=fully destroy",
    )


class ProductionPlan(BaseModel):
    """Validated creative production plan — never arbitrary SuperCollider code."""

    title: str
    description: str
    duration_seconds: float = Field(gt=0.0)
    global_parameters: GlobalParameters
    sections: list[ProductionSection] = Field(min_length=1)
    layers: list[AudioLayer] = Field(min_length=1)
    transitions: list[Transition] = Field(default_factory=list)
    narrative: str = ""
    variation_notes: str = ""

    @field_validator("title", "description")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value.strip()


def plan_summary_dict(plan: ProductionPlan) -> dict[str, Any]:
    """Compact metadata-safe summary (no huge nested dumps)."""
    return {
        "title": plan.title,
        "description": plan.description,
        "duration_seconds": plan.duration_seconds,
        "primary_mode": plan.global_parameters.primary_mode,
        "overall_intensity": plan.global_parameters.overall_intensity,
        "section_count": len(plan.sections),
        "layer_count": len(plan.layers),
        "layers": [layer.id for layer in plan.layers],
        "sections": [
            {
                "name": section.name,
                "start": section.start,
                "end": section.end,
                "energy": section.energy,
            }
            for section in plan.sections
        ],
    }
