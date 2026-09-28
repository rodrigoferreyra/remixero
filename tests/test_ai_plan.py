"""Tests for AI production plan validation and executor bridge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from noise_remix.ai.config import AIConfig, require_gemini_api_key
from noise_remix.ai.executor import plan_to_remix_parameters
from noise_remix.ai.registry import registry_processor_names
from noise_remix.ai.validate import validate_production_plan
from noise_remix.audio.analysis import analyze_audio
from noise_remix.errors import AIConfigError, ProductionPlanError
from noise_remix.models.production import (
    AudioLayer,
    GlobalParameters,
    ProductionPlan,
    ProductionSection,
)
from typer.testing import CliRunner

from noise_remix.cli.commands import app

FIXTURE = Path(__file__).parent / "fixtures" / "tone_1s.wav"
runner = CliRunner()


def _sample_plan(**overrides) -> ProductionPlan:
    data = {
        "title": "Industrial collapse",
        "description": "Sparse to dense destruction",
        "duration_seconds": 1.0,
        "global_parameters": GlobalParameters(
            overall_intensity=0.7,
            primary_mode="destroy",
            source_preservation=0.3,
        ),
        "sections": [
            ProductionSection(
                start=0.0,
                end=0.4,
                name="sparse",
                energy=0.3,
                active_layers=["grain"],
            ),
            ProductionSection(
                start=0.4,
                end=1.0,
                name="violence",
                energy=0.9,
                active_layers=["grain", "crush"],
            ),
        ],
        "layers": [
            AudioLayer(id="grain", processor="granular", intensity=0.4, start=0.0, end=1.0),
            AudioLayer(id="crush", processor="destroy", intensity=0.8, start=0.4, end=1.0),
        ],
        "narrative": "intact → destroyed",
    }
    data.update(overrides)
    return ProductionPlan.model_validate(data)


def test_registry_lists_executable_processors() -> None:
    names = set(registry_processor_names())
    assert {
        "granular",
        "destroy",
        "feedback",
        "collapse",
        "random",
        "passthrough",
        "comb",
        "ring_mod",
        "pitch_warp",
        "stutter",
        "pump",
    } <= names


def test_validate_drops_unknown_processor_layers() -> None:
    plan = _sample_plan()
    plan.layers[0].processor = "tape-eat"
    validated = validate_production_plan(plan, source_duration=1.0)
    assert all(layer.processor != "tape-eat" for layer in validated.layers)
    assert validated.layers  # crush layer remains


def test_validate_repairs_unknown_primary_mode() -> None:
    plan = _sample_plan()
    plan.global_parameters.primary_mode = "spectral-melt"
    validated = validate_production_plan(plan, source_duration=1.0)
    assert validated.global_parameters.primary_mode in {
        layer.processor for layer in validated.layers
    } | {"destroy"}


def test_validate_drops_unknown_layer_reference() -> None:
    plan = _sample_plan()
    plan.sections[0].active_layers = ["missing", "grain"]
    validated = validate_production_plan(plan, source_duration=1.0)
    assert validated.sections[0].active_layers == ["grain"]


def test_validate_maps_role_alias_layer_reference() -> None:
    plan = _sample_plan(
        layers=[
            AudioLayer(id="bed", processor="granular", intensity=0.4, start=0.0, end=1.0),
            AudioLayer(id="metal", processor="comb", intensity=0.7, start=0.0, end=1.0),
        ],
        sections=[
            ProductionSection(
                start=0.0,
                end=1.0,
                name="Build",
                energy=0.6,
                active_layers=["coloring", "bed"],
            )
        ],
        global_parameters=GlobalParameters(
            overall_intensity=0.6,
            primary_mode="granular",
            source_preservation=0.4,
        ),
    )
    validated = validate_production_plan(plan, source_duration=1.0)
    assert "bed" in validated.sections[0].active_layers
    assert "metal" in validated.sections[0].active_layers
    assert "coloring" not in validated.sections[0].active_layers


def test_validate_clamps_duration() -> None:
    plan = _sample_plan(duration_seconds=9.0)
    validated = validate_production_plan(plan, source_duration=1.0, max_duration=1.0)
    assert validated.duration_seconds == 1.0


def test_validate_clamps_feedback_parameter() -> None:
    from noise_remix.models.production import ParameterKV, ProcessingStep

    plan = _sample_plan()
    plan.layers[0].processing_chain = [
        ProcessingStep(
            processor="feedback",
            parameters=[
                ParameterKV(name="feedback", value=1.5),
                ParameterKV(name="intensity", value=2.0),
            ],
        )
    ]
    validated = validate_production_plan(plan, source_duration=1.0)
    params = validated.layers[0].processing_chain[0].parameters_as_dict()
    assert params["feedback"] <= 0.82
    assert params["intensity"] == 1.0


def test_developer_api_schema_strips_additional_properties() -> None:
    from noise_remix.ai.gemini import _developer_api_schema

    schema = _developer_api_schema(ProductionPlan)
    dumped = json.dumps(schema)
    assert "additionalProperties" not in dumped
    assert "additional_properties" not in dumped


def test_executor_builds_layered_render() -> None:
    from noise_remix.supercollider.generator import generate_patch

    analysis = analyze_audio(FIXTURE)
    plan = validate_production_plan(_sample_plan(), source_duration=analysis.duration)
    params = plan_to_remix_parameters(plan, analysis=analysis, seed=11)
    assert params.mode == "ai_plan"
    assert params.details.get("engine") == "layered"
    assert params.details.get("ai_render") == "layered"
    layers = params.details["layers"]
    assert len(layers) >= 2
    kinds = {layer["kind"] for layer in layers}
    assert "grains" in kinds
    assert "fragments" in kinds
    # Section gating: crush only in second section (around mid track).
    crush = next(layer for layer in layers if layer["id"] == "crush")
    assert crush["start"] >= 0.2
    assert float(crush.get("fade_out") or 0) > 0

    sc_text = generate_patch(
        params=params,
        input_wav=FIXTURE,
        output_wav=FIXTURE.with_name("out.wav"),
    )
    assert "remixero_master" in sc_text
    assert "remixero_grain" in sc_text
    assert "remixero_fragment" in sc_text
    assert "layered" in sc_text


def test_executor_honors_continuous_processors_and_overrides() -> None:
    from noise_remix.models.production import ParameterKV, ProcessingStep
    from noise_remix.supercollider.generator import generate_patch

    analysis = analyze_audio(FIXTURE)
    plan = _sample_plan(
        layers=[
            AudioLayer(
                id="bed",
                processor="pitch_warp",
                intensity=0.6,
                start=0.0,
                end=1.0,
                processing_chain=[
                    ProcessingStep(
                        processor="pitch_warp",
                        parameters=[
                            ParameterKV(name="pitch_ratio", value=0.5),
                            ParameterKV(name="wet", value=0.9),
                        ],
                    )
                ],
            ),
            AudioLayer(
                id="metal",
                processor="comb",
                intensity=0.7,
                start=0.2,
                end=1.0,
                processing_chain=[
                    ProcessingStep(
                        processor="comb",
                        parameters=[
                            ParameterKV(name="delay_time", value=0.04),
                            ParameterKV(name="decay", value=3.0),
                        ],
                    )
                ],
            ),
            AudioLayer(
                id="harsh",
                processor="ring_mod",
                intensity=0.5,
                start=0.5,
                end=1.0,
            ),
        ],
        sections=[
            ProductionSection(
                start=0.0,
                end=1.0,
                name="all",
                energy=0.8,
                active_layers=["bed", "metal", "harsh"],
            )
        ],
        global_parameters=GlobalParameters(
            overall_intensity=0.7,
            primary_mode="pitch_warp",
            source_preservation=0.2,
        ),
    )
    plan = validate_production_plan(plan, source_duration=analysis.duration)
    params = plan_to_remix_parameters(plan, analysis=analysis, seed=3)
    assert params.details["engine"] == "layered"
    by_id = {layer["id"]: layer for layer in params.details["layers"]}
    assert by_id["bed"]["details"]["pitch_ratio"] == 0.5
    assert by_id["metal"]["details"]["delay_time"] == 0.04
    assert by_id["harsh"]["kind"] == "ring_mod"

    sc_text = generate_patch(
        params=params,
        input_wav=FIXTURE,
        output_wav=FIXTURE.with_name("out2.wav"),
    )
    assert "remixero_pitchwarp" in sc_text
    assert "remixero_comb" in sc_text
    assert "remixero_ringmod" in sc_text


def test_brief_intent_boosts_hardcore_plans() -> None:
    from noise_remix.ai.brief import apply_brief_intent, classify_brief

    assert classify_brief("make it hardcore edm")["energy"] == "high"
    plan = validate_production_plan(_sample_plan(), source_duration=1.0)
    before_intensity = plan.global_parameters.overall_intensity
    before_layers = {layer.processor for layer in plan.layers}
    plan = apply_brief_intent(plan, "make it hardcore edm")
    plan = validate_production_plan(plan, source_duration=1.0)
    assert plan.global_parameters.overall_intensity >= max(before_intensity, 0.88)
    assert plan.global_parameters.source_preservation <= 0.22
    processors = {layer.processor for layer in plan.layers}
    assert "stutter" in processors or "stutter" in before_layers
    assert "destroy" in processors
    assert "pitch_warp" in processors


def test_align_plan_snaps_sections_and_adds_crossfades() -> None:
    from noise_remix.ai.timing import align_plan_to_analysis, envelope_gain_at
    from noise_remix.models.analysis import AmplitudeStats, AudioAnalysis, Segment

    analysis = AudioAnalysis(
        path="x.wav",
        duration=4.0,
        sample_rate=44100,
        channels=2,
        amplitude=AmplitudeStats(peak=0.5, rms=0.1, mean_abs=0.08),
        dynamic_range_db=12.0,
        dynamic_range_label="medium",
        spectral_centroid_hz=1000.0,
        spectral_flux=0.2,
        spectral_flux_label="low",
        transients=[1.0, 2.0, 3.0],
        segments=[
            Segment(start=0.0, end=1.0),
            Segment(start=1.0, end=2.0),
            Segment(start=2.0, end=4.0),
        ],
        estimated_bpm=120.0,
    )
    plan = ProductionPlan(
        title="t",
        description="d",
        duration_seconds=4.0,
        global_parameters=GlobalParameters(
            overall_intensity=0.7,
            primary_mode="destroy",
            source_preservation=0.3,
        ),
        sections=[
            ProductionSection(
                start=0.0, end=1.9, name="a", energy=0.4, active_layers=["g"]
            ),
            ProductionSection(
                start=1.9, end=4.0, name="b", energy=0.9, active_layers=["c"]
            ),
        ],
        layers=[
            AudioLayer(id="g", processor="granular", intensity=0.5),
            AudioLayer(id="c", processor="comb", intensity=0.7),
        ],
    )
    aligned = align_plan_to_analysis(plan, analysis)
    assert aligned.sections[0].end in {1.0, 2.0}
    assert aligned.sections[0].end == aligned.sections[1].start
    assert any(t.kind == "crossfade" and t.duration >= 0.35 for t in aligned.transitions)
    assert (
        envelope_gain_at(
            time=aligned.sections[0].end + 0.2,
            start=0.0,
            end=aligned.sections[0].end + 0.85,
            fade_in=0.2,
            fade_out=0.85,
        )
        < 1.0
    )


def test_layered_render_includes_fade_envelopes() -> None:
    from noise_remix.supercollider.generator import generate_patch

    analysis = analyze_audio(FIXTURE)
    plan = validate_production_plan(_sample_plan(), source_duration=analysis.duration)
    params = plan_to_remix_parameters(plan, analysis=analysis, seed=11)
    assert params.details.get("engine") == "layered"
    layers = params.details["layers"]
    assert layers
    assert any(float(layer.get("fade_out") or 0) >= 0.2 for layer in layers)
    assert "master" in params.details
    sc_text = generate_patch(
        params=params,
        input_wav=FIXTURE,
        output_wav=FIXTURE.with_name("fade-out.wav"),
    )
    assert "\\attack," in sc_text
    assert "\\release," in sc_text
    assert "remixero_master" in sc_text
    assert "drive" in sc_text


def test_automation_scales_event_amps() -> None:
    from noise_remix.ai.automation import apply_automation_to_layer_spec
    from noise_remix.models.production import AutomationEvent

    spec = {
        "kind": "fragments",
        "start": 0.0,
        "end": 1.0,
        "volume": 1.0,
        "intensity": 0.5,
        "details": {},
        "events": [
            {"onset": 0.1, "amp": 0.4, "dur": 0.05, "rate": 1.0, "pan": 0.0},
            {"onset": 0.8, "amp": 0.4, "dur": 0.05, "rate": 1.0, "pan": 0.0},
        ],
    }
    events = [
        AutomationEvent(target="volume", time=0.0, value=1.0, curve="linear"),
        AutomationEvent(target="volume", time=1.0, value=0.2, curve="linear"),
    ]
    out = apply_automation_to_layer_spec(spec, events=events)
    assert out["events"][0]["amp"] > out["events"][-1]["amp"]


def test_analysis_arrangement_builds_sections() -> None:
    from noise_remix.ai.arrange import apply_analysis_arrangement, propose_section_bounds

    analysis = analyze_audio(FIXTURE)
    bounds = propose_section_bounds(analysis, energy="high")
    assert len(bounds) >= 3
    plan = validate_production_plan(_sample_plan(), source_duration=analysis.duration)
    arranged = apply_analysis_arrangement(plan, analysis, energy="high")
    assert len(arranged.sections) >= 3
    assert arranged.sections[0].start == 0.0
    assert arranged.sections[-1].end == analysis.duration


def test_preview_option_in_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--preview" in result.stdout


def test_coerce_repairs_missing_sections() -> None:
    from noise_remix.ai.plan_parse import finalize_plan_payload

    analysis = analyze_audio(FIXTURE)
    payload = {
        "title": "No sections",
        "description": "model forgot sections",
        "duration_seconds": 1.0,
        "global_parameters": {
            "overall_intensity": 0.6,
            "primary_mode": "destroy",
            "source_preservation": 0.4,
        },
        "layers": [
            {"id": "crush", "processor": "destroy", "intensity": 0.8},
            {"id": "bed", "processor": "granular", "intensity": 0.4},
        ],
    }
    plan = finalize_plan_payload(payload, analysis=analysis, duration_seconds=1.0)
    assert plan.sections
    assert {layer.id for layer in plan.layers} == {"crush", "bed"}


def test_generate_plan_with_repairs_retries() -> None:
    from noise_remix.ai.plan_parse import generate_plan_with_repairs
    from noise_remix.audio.analysis import analyze_audio

    analysis = analyze_audio(FIXTURE)
    calls = {"n": 0}

    def request_once(correction: str | None) -> object:
        calls["n"] += 1
        if calls["n"] == 1:
            # Missing sections — should be repaired locally without needing retry,
            # so force a harder failure: empty layers after first attempt via garbage.
            return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": json.dumps({
                "title": "x",
                "description": "y",
                "duration_seconds": 1.0,
                "global_parameters": {
                    "overall_intensity": 0.5,
                    "primary_mode": "destroy",
                    "source_preservation": 0.5,
                },
                "layers": [],
                "sections": [{"start": 0, "end": 1, "name": "a", "active_layers": []}],
            })})()})()]})()
        assert correction is not None
        return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": json.dumps({
            "title": "Fixed",
            "description": "ok",
            "duration_seconds": 1.0,
            "global_parameters": {
                "overall_intensity": 0.5,
                "primary_mode": "destroy",
                "source_preservation": 0.5,
            },
            "layers": [{"id": "crush", "processor": "destroy", "intensity": 0.7}],
            "sections": [
                {
                    "start": 0.0,
                    "end": 1.0,
                    "name": "full",
                    "active_layers": ["crush"],
                }
            ],
        })})()})()]})()

    from noise_remix.ai.plan_parse import payload_from_chat_response

    plan = generate_plan_with_repairs(
        request_once=request_once,
        extract_payload=payload_from_chat_response,
        analysis=analysis,
        duration_seconds=1.0,
        provider_label="Test",
        max_attempts=3,
    )
    assert plan.title == "Fixed"
    assert calls["n"] == 2


def test_missing_api_key() -> None:
    with pytest.raises(AIConfigError, match="GEMINI_API_KEY"):
        require_gemini_api_key(AIConfig(provider="gemini", api_key=None))


def test_missing_groq_api_key() -> None:
    from noise_remix.ai.config import require_api_key

    with pytest.raises(AIConfigError, match="GROQ_API_KEY"):
        require_api_key(AIConfig(provider="groq", api_key=None, model="openai/gpt-oss-20b"))


def test_auto_provider_prefers_groq_when_only_groq_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from noise_remix.ai.config import load_ai_config

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("REMIXERO_AI_PROVIDER", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    config = load_ai_config()
    assert config.provider == "groq"
    assert config.model == "openai/gpt-oss-20b"
    assert config.api_key == "test-key"


def test_provider_override_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    from noise_remix.ai.config import load_ai_config

    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("GEMINI_API_KEY", "m")
    config = load_ai_config(provider_override="groq")
    assert config.provider == "groq"
    assert config.api_key == "g"


def test_groq_json_format_error_detection() -> None:
    from noise_remix.ai.groq_client import _looks_like_json_format_error

    assert _looks_like_json_format_error(
        Exception(
            "Error code: 400 - {'error': {'message': \"Failed to validate JSON. "
            "Please adjust your prompt. See 'failed_generation' for more details.\", "
            "'type': 'invalid_request_error', 'code': 'json_validate_failed', "
            "'failed_generation': ''}}"
        )
    )
    assert not _looks_like_json_format_error(Exception("503 UNAVAILABLE"))


def test_transient_error_detection() -> None:
    from noise_remix.ai.retry import is_transient_ai_error

    assert is_transient_ai_error(
        Exception("503 UNAVAILABLE. This model is currently experiencing high demand.")
    )
    assert is_transient_ai_error(Exception("429 RESOURCE_EXHAUSTED"))
    assert not is_transient_ai_error(Exception("400 INVALID_ARGUMENT"))


def test_generate_retries_on_503(monkeypatch: pytest.MonkeyPatch) -> None:
    from noise_remix.ai.retry import call_with_retries

    calls = {"n": 0}
    sleeps: list[float] = []

    def operation():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("503 UNAVAILABLE high demand try again later")
        return "ok"

    monkeypatch.setattr("noise_remix.ai.retry.time.sleep", lambda s: sleeps.append(s))
    assert (
        call_with_retries(
            operation=operation,
            max_retries=4,
            retry_base_seconds=0.01,
            retry_max_seconds=0.05,
            provider_label="Test",
        )
        == "ok"
    )
    assert calls["n"] == 3
    assert len(sleeps) == 2


def test_generate_exhausts_retries_on_503(monkeypatch: pytest.MonkeyPatch) -> None:
    from noise_remix.ai.retry import call_with_retries
    from noise_remix.errors import AIRequestError

    monkeypatch.setattr("noise_remix.ai.retry.time.sleep", lambda s: None)
    with pytest.raises(AIRequestError, match="after 3 attempts"):
        call_with_retries(
            operation=lambda: (_ for _ in ()).throw(
                RuntimeError("503 UNAVAILABLE high demand")
            ),
            max_retries=2,
            retry_base_seconds=0.01,
            retry_max_seconds=0.05,
            provider_label="Test",
        )


def test_ai_requires_prompt_non_tty() -> None:
    result = runner.invoke(app, [str(FIXTURE), "--ai", "--yes"])
    assert result.exit_code == 1
    assert "prompt" in result.stdout.lower() or "instruction" in result.stdout.lower()


def test_non_ai_modes_still_work_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--ai" in result.stdout
    assert "--prompt" in result.stdout
    assert "--provider" in result.stdout
    assert "--keep-plan" in result.stdout
    assert "--hybrid-listen" in result.stdout


def test_prompt_includes_listening_brief() -> None:
    from noise_remix.ai.listen import ListeningBrief, SalientMoment
    from noise_remix.ai.prompts import build_user_prompt

    analysis = analyze_audio(FIXTURE)
    brief = ListeningBrief(
        summary="Dense industrial track with shouted vocals.",
        structure_notes="Intro then verse/chorus loop.",
        salient_moments=[SalientMoment(time=0.2, label="vocal entry")],
        preserve="kick pulse",
        destroy="pad wash",
        energy_curve="builds mid-track",
    )
    prompt = build_user_prompt(
        instruction="make the chorus hardcore",
        analysis=analysis,
        duration_seconds=analysis.duration,
        variation_index=0,
        variations=1,
        listening_brief=brief,
    )
    assert "Gemini listening notes" in prompt
    assert "Dense industrial track" in prompt
    assert "vocal entry" in prompt
    assert "kick pulse" in prompt


def test_director_skips_listen_without_gemini_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from noise_remix.ai.director import generate_production_plan

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    analysis = analyze_audio(FIXTURE)
    statuses: list[str] = []
    captured: dict = {}

    def fake_groq(**kwargs):
        captured["listening_brief"] = kwargs.get("listening_brief")
        return _sample_plan(duration_seconds=analysis.duration)

    monkeypatch.setattr(
        "noise_remix.ai.groq_client.generate_production_plan_groq",
        fake_groq,
    )
    plan = generate_production_plan(
        audio_path=FIXTURE,
        analysis=analysis,
        instruction="destroy",
        duration_seconds=analysis.duration,
        config=AIConfig(provider="groq", api_key="g", model="openai/gpt-oss-20b"),
        hybrid_listen=True,
        status=statuses.append,
    )
    assert plan.title
    assert captured["listening_brief"] is None
    assert any("Listen skipped" in message for message in statuses)


def test_director_skips_listen_by_default_even_with_gemini_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from noise_remix.ai.director import generate_production_plan

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    analysis = analyze_audio(FIXTURE)
    listen_calls = {"n": 0}
    captured: dict = {}

    def fake_listen(**_kwargs):
        listen_calls["n"] += 1
        return None

    monkeypatch.setattr(
        "noise_remix.ai.director.generate_listening_brief",
        fake_listen,
    )

    def fake_groq(**kwargs):
        captured["listening_brief"] = kwargs.get("listening_brief")
        return _sample_plan(duration_seconds=analysis.duration)

    monkeypatch.setattr(
        "noise_remix.ai.groq_client.generate_production_plan_groq",
        fake_groq,
    )

    plan = generate_production_plan(
        audio_path=FIXTURE,
        analysis=analysis,
        instruction="destroy",
        duration_seconds=analysis.duration,
        config=AIConfig(provider="groq", api_key="g", model="openai/gpt-oss-20b"),
        hybrid_listen=False,
    )
    assert plan.title
    assert listen_calls["n"] == 0
    assert captured["listening_brief"] is None


def test_listen_failure_returns_none_softly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from noise_remix.ai.listen import generate_listening_brief

    analysis = analyze_audio(FIXTURE)

    def boom(*_args, **_kwargs):
        raise RuntimeError("upload failed")

    monkeypatch.setattr(
        "noise_remix.ai.listen.call_with_retries",
        boom,
    )
    # Fail before upload by making Client raise.
    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        class files:
            @staticmethod
            def upload(**_kwargs):
                raise RuntimeError("no upload")

    monkeypatch.setitem(
        __import__("sys").modules,
        "google.genai",
        type("M", (), {"Client": FakeClient, "types": object()})(),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "google",
        type("G", (), {"genai": __import__("sys").modules["google.genai"]})(),
    )

    brief = generate_listening_brief(
        audio_path=FIXTURE,
        analysis=analysis,
        instruction="listen",
        config=AIConfig(
            provider="gemini",
            api_key="fake",
            model="gemini-3.8-flash",
        ),
    )
    assert brief is None


def test_director_passes_listening_brief_to_groq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from noise_remix.ai.director import generate_production_plan
    from noise_remix.ai.listen import ListeningBrief

    analysis = analyze_audio(FIXTURE)
    brief = ListeningBrief(
        summary="Chorus at 12s with big snare.",
        preserve="snare",
        destroy="pads",
    )
    statuses: list[str] = []
    captured: dict = {}

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setattr(
        "noise_remix.ai.director.load_gemini_listen_config",
        lambda: AIConfig(
            provider="gemini",
            api_key="gemini-test-key",
            model="gemini-3.8-flash",
        ),
    )
    monkeypatch.setattr(
        "noise_remix.ai.director.generate_listening_brief",
        lambda **_kwargs: brief,
    )

    def fake_groq(**kwargs):
        captured["listening_brief"] = kwargs.get("listening_brief")
        return _sample_plan(duration_seconds=analysis.duration)

    monkeypatch.setattr(
        "noise_remix.ai.groq_client.generate_production_plan_groq",
        fake_groq,
    )

    plan = generate_production_plan(
        audio_path=FIXTURE,
        analysis=analysis,
        instruction="hardcore chorus",
        duration_seconds=analysis.duration,
        config=AIConfig(provider="groq", api_key="g", model="openai/gpt-oss-20b"),
        hybrid_listen=True,
        status=statuses.append,
    )
    assert plan.title
    assert captured["listening_brief"] is brief
    assert any("Listening notes attached" in message for message in statuses)


def test_director_skips_separate_listen_for_gemini_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from noise_remix.ai.director import generate_production_plan

    analysis = analyze_audio(FIXTURE)
    statuses: list[str] = []
    listen_calls = {"n": 0}

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")

    def fake_listen(**_kwargs):
        listen_calls["n"] += 1
        return None

    monkeypatch.setattr(
        "noise_remix.ai.director.generate_listening_brief",
        fake_listen,
    )

    def fake_gemini(**kwargs):
        assert kwargs.get("listening_brief") is None
        return _sample_plan(duration_seconds=analysis.duration)

    monkeypatch.setattr(
        "noise_remix.ai.gemini.generate_production_plan",
        fake_gemini,
    )

    plan = generate_production_plan(
        audio_path=FIXTURE,
        analysis=analysis,
        instruction="sparse then violent",
        duration_seconds=analysis.duration,
        config=AIConfig(
            provider="gemini",
            api_key="gemini-test-key",
            model="gemini-3.8-flash",
        ),
        hybrid_listen=True,
        status=statuses.append,
    )
    assert plan.title
    assert listen_calls["n"] == 0
    assert any("separate listen skipped" in message for message in statuses)
