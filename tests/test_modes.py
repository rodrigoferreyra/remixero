"""Unit tests for additional remix modes."""

from __future__ import annotations

from pathlib import Path

from noise_remix.audio.analysis import analyze_audio
from noise_remix.remix import available_modes, get_mode
from noise_remix.remix.feedback import MAX_FEEDBACK
from noise_remix.supercollider.generator import generate_patch

FIXTURE = Path(__file__).parent / "fixtures" / "tone_1s.wav"


def test_available_modes_include_mvp_set() -> None:
    modes = set(available_modes())
    assert {
        "smoke",
        "granular",
        "destroy",
        "collapse",
        "feedback",
        "random",
        "comb",
        "ring_mod",
        "pitch_warp",
        "stutter",
        "pump",
    } <= modes


def test_destroy_intensity_changes_params() -> None:
    analysis = analyze_audio(FIXTURE)
    mode = get_mode("destroy")
    soft = mode.generate(analysis=analysis, intensity=0.1, seed=9, duration=1.0)
    hard = mode.generate(analysis=analysis, intensity=0.95, seed=9, duration=1.0)
    assert soft.details["density"] < hard.details["density"]
    assert soft.details["distort"] < hard.details["distort"]
    assert soft.details["events"] == mode.generate(
        analysis=analysis, intensity=0.1, seed=9, duration=1.0
    ).details["events"]


def test_random_is_seeded_not_arbitrary() -> None:
    analysis = analyze_audio(FIXTURE)
    mode = get_mode("random")
    a = mode.generate(analysis=analysis, intensity=0.7, seed=101, duration=0.8)
    b = mode.generate(analysis=analysis, intensity=0.7, seed=101, duration=0.8)
    c = mode.generate(analysis=analysis, intensity=0.7, seed=202, duration=0.8)
    assert a.details == b.details
    assert a.details["events"] != c.details["events"]
    assert "primitives" in a.details


def test_collapse_progresses_via_events() -> None:
    analysis = analyze_audio(FIXTURE)
    params = get_mode("collapse").generate(
        analysis=analysis, intensity=0.8, seed=3, duration=1.0
    )
    events = params.details["events"]
    assert events
    assert params.details["feedback_amount"] <= 0.55
    # Later events should tend shorter on average than early ones.
    early = events[: max(1, len(events) // 4)]
    late = events[-(max(1, len(events) // 4)) :]
    early_dur = sum(e["dur"] for e in early) / len(early)
    late_dur = sum(e["dur"] for e in late) / len(late)
    assert late_dur <= early_dur * 1.05


def test_feedback_is_bounded() -> None:
    analysis = analyze_audio(FIXTURE)
    mode = get_mode("feedback")
    params = mode.generate(analysis=analysis, intensity=1.0, seed=5, duration=1.0)
    assert params.details["feedback"] <= MAX_FEEDBACK
    text = generate_patch(
        params=params,
        input_wav=FIXTURE,
        output_wav=Path("/tmp/remixero-feedback-out.wav"),
    )
    assert "Limiter.ar" in text
    assert "LocalIn.ar" in text
    assert "remixero_feedback" in text
    # pan/amp must be SynthDef controls — undeclared names hang SC NRT.
    assert "amp=0.85, pan=0" in text
    assert "RandSeed.ir(1, randSeed)" not in text


def test_destroy_patch_generation() -> None:
    analysis = analyze_audio(FIXTURE)
    params = get_mode("destroy").generate(
        analysis=analysis, intensity=0.8, seed=11, duration=0.6
    )
    text = generate_patch(
        params=params,
        input_wav=FIXTURE,
        output_wav=Path("/tmp/remixero-destroy-out.wav"),
    )
    assert "remixero_fragment" in text
    assert "Limiter.ar" in text


def test_new_continuous_modes_generate_patches() -> None:
    analysis = analyze_audio(FIXTURE)
    for mode_name, marker in (
        ("comb", "CombC.ar"),
        ("ring_mod", "SinOsc.ar"),
        ("pitch_warp", "PitchShift.ar"),
        ("pump", "LFPulse.kr"),
    ):
        params = get_mode(mode_name).generate(
            analysis=analysis, intensity=0.7, seed=7, duration=0.5
        )
        text = generate_patch(
            params=params,
            input_wav=FIXTURE,
            output_wav=Path(f"/tmp/remixero-{mode_name}-out.wav"),
        )
        assert marker in text
        assert "Limiter.ar" in text


def test_stutter_builds_held_events() -> None:
    analysis = analyze_audio(FIXTURE)
    params = get_mode("stutter").generate(
        analysis=analysis, intensity=0.8, seed=13, duration=0.8
    )
    events = params.details["events"]
    assert len(events) >= 4
    # High hold probability should repeat some buffer positions.
    positions = [event["buf_pos"] for event in events]
    assert len(set(positions)) < len(positions)


def test_rand_depth_scales_with_intensity() -> None:
    from noise_remix.remix.chaos import rand_depth

    assert rand_depth(0.0) == 0.05
    assert rand_depth(1.0) == 0.85
    assert rand_depth(0.0) < rand_depth(0.5) < rand_depth(1.0)


def test_modes_record_rand_depth_and_are_seed_deterministic() -> None:
    analysis = analyze_audio(FIXTURE)
    for name in ("granular", "destroy", "feedback", "comb", "pump"):
        mode = get_mode(name)
        a = mode.generate(analysis=analysis, intensity=0.7, seed=123, duration=1.0)
        b = mode.generate(analysis=analysis, intensity=0.7, seed=123, duration=1.0)
        assert a.details["rand_depth"] == b.details["rand_depth"]
        assert 0.05 <= float(a.details["rand_depth"]) <= 0.85
        # Parameter payloads match for the same seed.
        assert a.model_dump() == b.model_dump()


def test_generated_patches_include_seeded_sc_randomness() -> None:
    analysis = analyze_audio(FIXTURE)
    out = Path("/tmp/remixero-rand-test.wav")
    for name in ("granular", "destroy", "feedback", "pump"):
        params = get_mode(name).generate(
            analysis=analysis, intensity=0.8, seed=42, duration=1.0
        )
        text = generate_patch(params=params, input_wav=FIXTURE, output_wav=out)
        assert "RandSeed" in text
        assert "remixero_randseed" in text
        assert "LFNoise1" in text
        assert "\\randDepth" in text
        assert float(params.details["rand_depth"]) > 0.0


def test_low_intensity_still_emits_rand_controls_with_small_depth() -> None:
    analysis = analyze_audio(FIXTURE)
    params = get_mode("feedback").generate(
        analysis=analysis, intensity=0.0, seed=7, duration=1.0
    )
    assert params.details["rand_depth"] == 0.05
    text = generate_patch(
        params=params,
        input_wav=FIXTURE,
        output_wav=Path("/tmp/remixero-rand-low.wav"),
    )
    assert "\\randDepth, 0.050000" in text
    assert "RandSeed" in text
