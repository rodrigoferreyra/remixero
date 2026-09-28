"""Compact JSON schemas for Groq (avoid brittle full Pydantic/$defs schemas)."""

from __future__ import annotations

# Hand-written, shallow schema. Groq's json_schema validator often rejects or
# empties generations against large Pydantic schemas with $ref/$defs.
GROQ_PRODUCTION_PLAN_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "duration_seconds": {"type": "number"},
        "global_parameters": {
            "type": "object",
            "properties": {
                "overall_intensity": {"type": "number"},
                "primary_mode": {"type": "string"},
                "source_preservation": {"type": "number"},
            },
            "required": [
                "overall_intensity",
                "primary_mode",
                "source_preservation",
            ],
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "name": {"type": "string"},
                    "energy": {"type": "number"},
                    "description": {"type": "string"},
                    "active_layers": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["start", "end", "name", "active_layers"],
            },
        },
        "layers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "processor": {"type": "string"},
                    "intensity": {"type": "number"},
                    "volume": {"type": "number"},
                    "pan": {"type": "number"},
                    "start": {"type": "number"},
                    "end": {"type": ["number", "null"]},
                    "notes": {"type": "string"},
                    "processing_chain": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "processor": {"type": "string"},
                                "parameters": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "value": {},
                                        },
                                        "required": ["name", "value"],
                                    },
                                },
                            },
                            "required": ["processor"],
                        },
                    },
                },
                "required": ["id", "processor"],
            },
        },
        "transitions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "at": {"type": "number"},
                    "kind": {"type": "string"},
                    "description": {"type": "string"},
                    "duration": {"type": "number"},
                },
                "required": ["at", "kind"],
            },
        },
        "narrative": {"type": "string"},
        "variation_notes": {"type": "string"},
    },
    "required": [
        "title",
        "description",
        "duration_seconds",
        "global_parameters",
        "sections",
        "layers",
    ],
}
