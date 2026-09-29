"""Generate SuperCollider source for rendering."""

from __future__ import annotations

from pathlib import Path

from noise_remix.models.configuration import RemixParameters


def escape_sc_string(value: str) -> str:
    """Escape a Python string for inclusion in a SuperCollider double-quoted string."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _sc_seed(seed: int) -> int:
    """Fit a Remixero seed into a non-negative 31-bit SuperCollider RandSeed value."""
    return abs(int(seed)) & 0x7FFFFFFF


def _details_rand_depth(details: object, *, intensity: float = 0.5) -> float:
    if isinstance(details, dict) and "rand_depth" in details:
        return max(0.0, min(1.0, float(details["rand_depth"])))
    from noise_remix.remix.chaos import rand_depth

    return rand_depth(intensity)


def _rand_seed_score_events(seed: int) -> list[str]:
    """Emit a one-shot SynthDef that seeds the server RNG for NRT reproducibility."""
    seed_i = _sc_seed(seed)
    return [
        (
            "\t[0.0, ['/d_recv', SynthDef(\\remixero_randseed, { |seed=0|\n"
            "\t\t\tRandSeed.ir(1, seed);\n"
            "\t}).asBytes]],"
        ),
        f"\t[0.0, [\\s_new, \\remixero_randseed, 800, 0, 0, \\seed, {seed_i}]],",
    ]


def _rand_mod_prefix_light() -> str:
    """Cheap modulation for short grain/fragment voices (many concurrent nodes).

    Relies on the score-level ``remixero_randseed`` synth for reproducibility.
    Avoids per-voice RandSeed/Dust which make dense NRT scores extremely slow.
    All lines must be ``var`` declarations — SuperCollider forbids statements
    before later ``var`` lines in the same SynthDef.
    """
    return (
        "\t\t\tvar chaos = randDepth.max(0).min(1);\n"
        "\t\t\tvar rateMod = 1 + (LFNoise1.kr(6 + (chaos * 10)) * chaos * 0.28);\n"
        "\t\t\tvar panMod = (pan + (LFNoise1.kr(3 + (chaos * 6)) * chaos * 0.35)).clip(-1, 1);\n"
        "\t\t\tvar ampMod = amp * (1 + (LFNoise1.kr(4) * chaos * 0.18));\n"
    )


def _rand_mod_prefix() -> str:
    """Fuller modulation for long-lived continuous layers (few concurrent nodes).

    Do not insert non-``var`` statements here — continuous bodies declare more
    ``var``s immediately after this prefix. Server RNG is seeded once per score.

    Callers must declare ``pan`` and ``amp`` SynthDef controls — undeclared
    names hang SuperCollider NRT instead of failing cleanly.
    """
    return (
        "\t\t\tvar chaos = randDepth.max(0).min(1);\n"
        "\t\t\tvar dustTrig = Dust.kr(0.15 + (chaos * 2.5));\n"
        "\t\t\tvar jump = TRand.kr(0.85, 1.2, dustTrig);\n"
        "\t\t\tvar rateMod = (1 + (LFNoise1.kr(8 + (chaos * 18)) * chaos * 0.35))"
        " * (1.0 + ((jump - 1.0) * chaos));\n"
        "\t\t\tvar panMod = (pan + (LFNoise1.kr(4 + (chaos * 10)) * chaos * 0.45)).clip(-1, 1);\n"
        "\t\t\tvar ampMod = amp * (1 + (LFNoise1.kr(6) * chaos * 0.22));\n"
    )


def generate_patch(
    *,
    params: RemixParameters,
    input_wav: Path,
    output_wav: Path,
) -> str:
    """Dispatch SuperCollider generation from structured remix parameters."""
    engine = params.details.get("engine")
    if engine == "layered" or params.mode == "ai_plan":
        return generate_layered_patch(
            params=params,
            input_wav=input_wav,
            output_wav=output_wav,
        )
    if params.mode == "smoke":
        return generate_passthrough_patch(
            input_wav=input_wav,
            output_wav=output_wav,
            duration=params.duration,
            sample_rate=params.sample_rate,
            channels=params.channels,
        )
    if params.mode == "granular":
        return generate_granular_patch(
            params=params,
            input_wav=input_wav,
            output_wav=output_wav,
        )
    if engine == "fragments" or params.mode in {
        "destroy",
        "collapse",
        "random",
        "stutter",
    }:
        return generate_fragment_patch(
            params=params,
            input_wav=input_wav,
            output_wav=output_wav,
        )
    if engine == "feedback" or params.mode == "feedback":
        return generate_feedback_patch(
            params=params,
            input_wav=input_wav,
            output_wav=output_wav,
        )
    if engine == "comb" or params.mode == "comb":
        return generate_comb_patch(
            params=params,
            input_wav=input_wav,
            output_wav=output_wav,
        )
    if engine == "ring_mod" or params.mode == "ring_mod":
        return generate_ring_mod_patch(
            params=params,
            input_wav=input_wav,
            output_wav=output_wav,
        )
    if engine == "pitch_warp" or params.mode == "pitch_warp":
        return generate_pitch_warp_patch(
            params=params,
            input_wav=input_wav,
            output_wav=output_wav,
        )
    if engine == "pump" or params.mode == "pump":
        return generate_pump_patch(
            params=params,
            input_wav=input_wav,
            output_wav=output_wav,
        )
    raise ValueError(f"No SuperCollider generator for mode '{params.mode}'")


def generate_passthrough_patch(
    *,
    input_wav: Path,
    output_wav: Path,
    duration: float,
    sample_rate: int,
    channels: int,
) -> str:
    """Generate a readable NRT pass-through patch with output limiting."""
    if duration <= 0:
        raise ValueError("duration must be positive")
    if channels < 1:
        raise ValueError("channels must be >= 1")

    in_path = escape_sc_string(str(input_wav.resolve()))
    out_path = escape_sc_string(str(output_wav.resolve()))
    channel_list = ", ".join(str(i) for i in range(channels))
    spatial = "sig ! 2" if channels == 1 else "sig[0..1]"

    return f"""\
// Remixero smoke render — pass-through with limiter
// Generated for inspection; safe to edit manually.
(
var server, score, duration, sampleRate, numInputChannels;
duration = {duration:.6f};
sampleRate = {sample_rate};
numInputChannels = {channels};

server = Server(
	\\remixero_nrt,
	options: ServerOptions.new
		.numOutputBusChannels_(2)
		.numInputBusChannels_(numInputChannels)
		.sampleRate_(sampleRate)
);

score = Score([
	[0.0, [
		'/d_recv',
		SynthDef(\\remixero_passthrough, {{
			var sig = SoundIn.ar([{channel_list}]);
			var limited = Limiter.ar({spatial}, 0.95);
			Out.ar(0, limited);
		}}).asBytes
	]],
	[0.0, Synth.basicNew(\\remixero_passthrough, server).newMsg],
	[duration, [\\c_set, 0, 0]]
]);

score.recordNRT(
	outputFilePath: "{out_path}",
	inputFilePath: "{in_path}",
	sampleRate: sampleRate,
	headerFormat: "WAV",
	sampleFormat: "int16",
	options: server.options,
	duration: duration,
	action: {{
		server.remove;
		0.exit;
	}}
);
)
"""


def generate_granular_patch(
    *,
    params: RemixParameters,
    input_wav: Path,
    output_wav: Path,
) -> str:
    """Generate an inspectable NRT granular Score from structured grain events."""
    grains = params.details.get("grains") or []
    if not isinstance(grains, list) or not grains:
        raise ValueError("granular parameters must include a non-empty grains list")

    in_path = escape_sc_string(str(input_wav.resolve()))
    out_path = escape_sc_string(str(output_wav.resolve()))
    channels = params.channels
    sample_rate = params.sample_rate
    duration = params.duration

    rand_d = _details_rand_depth(params.details, intensity=params.intensity)

    if channels == 1:
        play_lines = (
            f"{_rand_mod_prefix_light()}"
            "\t\t\tvar playRate = rate * rateMod;\n"
            "\t\t\tvar sig = PlayBuf.ar(1, buf, playRate * BufRateScale.kr(buf), 1, startPos, loop: 0);\n"
            "\t\t\tvar env = EnvGen.kr(Env.linen(attack, sustain, release), doneAction: 2);\n"
            "\t\t\tvar limited = Limiter.ar(Pan2.ar(sig, panMod, ampMod) * env, 0.95);\n"
            "\t\t\tOut.ar(out, limited);"
        )
    else:
        play_lines = (
            f"{_rand_mod_prefix_light()}"
            "\t\t\tvar playRate = rate * rateMod;\n"
            "\t\t\tvar sig = PlayBuf.ar(2, buf, playRate * BufRateScale.kr(buf), 1, startPos, loop: 0);\n"
            "\t\t\tvar env = EnvGen.kr(Env.linen(attack, sustain, release), doneAction: 2);\n"
            "\t\t\tvar limited = Limiter.ar(Balance2.ar(sig[0], sig[1], panMod, ampMod) * env, 0.95);\n"
            "\t\t\tOut.ar(out, limited);"
        )

    events: list[str] = [
        "\t[0.0, ['/d_recv', SynthDef(\\remixero_grain, {"
        " |out=0, buf=0, startPos=0, rate=1, attack=0.005, sustain=0.05, release=0.02, "
        "amp=0.2, pan=0, randDepth=0, randSeed=0|\n"
        f"{play_lines}\n"
        "\t}).asBytes]],",
        f'\t[0.0, ["/b_allocRead", 0, "{in_path}"]],',
    ]

    node_id = 1000
    time_offset = 0.05
    for grain in grains:
        onset = float(grain["onset"]) + time_offset
        buf_pos = float(grain["buf_pos"])
        dur = float(grain["dur"])
        rate = float(grain["rate"])
        pan = float(grain["pan"])
        amp = float(grain["amp"])
        start_samples = int(round(buf_pos * sample_rate))
        attack = min(0.01, dur * 0.2)
        release = min(0.03, dur * 0.3)
        sustain = max(0.005, dur - attack - release)
        grain_seed = _sc_seed(params.seed ^ node_id)
        events.append(
            f"\t[{onset:.6f}, [\\s_new, \\remixero_grain, {node_id}, 0, 0, "
            f"\\buf, 0, \\startPos, {start_samples}, \\rate, {rate:.6f}, "
            f"\\attack, {attack:.6f}, \\sustain, {sustain:.6f}, \\release, {release:.6f}, "
            f"\\amp, {amp:.6f}, \\pan, {pan:.6f}, "
            f"\\randDepth, {rand_d:.6f}, \\randSeed, {grain_seed}]],"
        )
        node_id += 1

    render_duration = duration + time_offset + 0.05
    events.append(f"\t[{render_duration:.6f}, [\\c_set, 0, 0]]")
    return _wrap_score(
        mode=params.mode,
        intensity=params.intensity,
        seed=params.seed,
        sample_rate=sample_rate,
        render_duration=render_duration,
        out_path=out_path,
        score_body="\n".join(events),
    )


def generate_fragment_patch(
    *,
    params: RemixParameters,
    input_wav: Path,
    output_wav: Path,
) -> str:
    """NRT fragment player with filtering, soft clipping, and limiting."""
    fragment_events = params.details.get("events") or []
    if not isinstance(fragment_events, list) or not fragment_events:
        raise ValueError(f"{params.mode} parameters must include a non-empty events list")

    in_path = escape_sc_string(str(input_wav.resolve()))
    out_path = escape_sc_string(str(output_wav.resolve()))
    channels = params.channels
    sample_rate = params.sample_rate
    duration = params.duration
    feedback_amount = float(params.details.get("feedback_amount") or 0.0)
    feedback_amount = max(0.0, min(0.55, feedback_amount))

    rand_d = _details_rand_depth(params.details, intensity=params.intensity)

    if channels == 1:
        read_sig = (
            "PlayBuf.ar(1, buf, (rate * rateMod) "
            "* BufRateScale.kr(buf), 1, startPos, loop: 0)"
        )
        spatialize = "Pan2.ar(sig, panMod, ampMod)"
    else:
        read_sig = (
            "PlayBuf.ar(2, buf, (rate * rateMod) "
            "* BufRateScale.kr(buf), 1, startPos, loop: 0)"
        )
        spatialize = "Balance2.ar(sig[0], sig[1], panMod, ampMod)"

    play_lines = f"""\
{_rand_mod_prefix_light()}\
			var dry = {read_sig};
			var env = EnvGen.kr(Env.linen(attack, sustain, release), doneAction: 2);
			var lpfMod = (lpf * (1.0 + (LFNoise1.kr(0.7 + chaos) * chaos * 0.35))).clip(200, 18000);
			var hpfMod = (hpf * (1.0 + (LFNoise1.kr(0.5 + chaos) * chaos * 0.25))).clip(20, 4000);
			var shaped = HPF.ar(LPF.ar(dry, lpfMod), hpfMod);
			var driven = (shaped * (1.0 + (distort * 8.0))).tanh;
			var sig = driven;
			var wet = DelayC.ar(sig, 0.3, 0.12) * feedbackAmt;
			var mixed = ({spatialize} + Pan2.ar(wet, panMod * 0.5, ampMod * 0.5)) * env;
			var limited = Limiter.ar(mixed, 0.95);
			Out.ar(out, limited);"""

    events: list[str] = [
        "\t[0.0, ['/d_recv', SynthDef(\\remixero_fragment, {"
        " |out=0, buf=0, startPos=0, rate=1, attack=0.002, sustain=0.05, release=0.01, "
        "amp=0.2, pan=0, distort=0, lpf=12000, hpf=40, feedbackAmt=0, randDepth=0, randSeed=0|\n"
        f"{play_lines}\n"
        "\t}).asBytes]],",
        f'\t[0.0, ["/b_allocRead", 0, "{in_path}"]],',
    ]

    node_id = 1000
    time_offset = 0.05
    for item in fragment_events:
        onset = float(item["onset"]) + time_offset
        start_samples = int(round(float(item["buf_pos"]) * sample_rate))
        dur = float(item["dur"])
        attack = min(0.008, dur * 0.15)
        release = min(0.025, dur * 0.25)
        sustain = max(0.004, dur - attack - release)
        frag_seed = _sc_seed(params.seed ^ node_id)
        events.append(
            f"\t[{onset:.6f}, [\\s_new, \\remixero_fragment, {node_id}, 0, 0, "
            f"\\buf, 0, \\startPos, {start_samples}, \\rate, {float(item['rate']):.6f}, "
            f"\\attack, {attack:.6f}, \\sustain, {sustain:.6f}, \\release, {release:.6f}, "
            f"\\amp, {float(item['amp']):.6f}, \\pan, {float(item['pan']):.6f}, "
            f"\\distort, {float(item['distort']):.6f}, \\lpf, {float(item['lpf']):.3f}, "
            f"\\hpf, {float(item['hpf']):.3f}, \\feedbackAmt, {feedback_amount:.6f}, "
            f"\\randDepth, {rand_d:.6f}, \\randSeed, {frag_seed}]],"
        )
        node_id += 1

    render_duration = duration + time_offset + 0.05
    events.append(f"\t[{render_duration:.6f}, [\\c_set, 0, 0]]")
    return _wrap_score(
        mode=params.mode,
        intensity=params.intensity,
        seed=params.seed,
        sample_rate=sample_rate,
        render_duration=render_duration,
        out_path=out_path,
        score_body="\n".join(events),
    )


def generate_feedback_patch(
    *,
    params: RemixParameters,
    input_wav: Path,
    output_wav: Path,
) -> str:
    """Continuous buffer playback through a bounded feedback loop with limiting."""
    details = params.details
    feedback = float(details["feedback"])
    max_feedback = float(details.get("max_feedback") or 0.82)
    feedback = max(0.0, min(max_feedback, feedback))
    delay_time = max(0.01, min(0.45, float(details["delay_time"])))
    drive = max(0.5, min(6.0, float(details["drive"])))
    lpf = max(200.0, min(18000.0, float(details["lpf"])))
    hpf = max(20.0, min(4000.0, float(details["hpf"])))
    rate = max(0.5, min(1.5, float(details.get("playback_rate") or 1.0)))
    pitch_dispersion = max(0.0, min(0.2, float(details.get("pitch_dispersion") or 0.0)))

    in_path = escape_sc_string(str(input_wav.resolve()))
    out_path = escape_sc_string(str(output_wav.resolve()))
    channels = params.channels
    sample_rate = params.sample_rate
    duration = params.duration

    rand_d = _details_rand_depth(details, intensity=params.intensity)

    if channels == 1:
        src_line = (
            "var src = PlayBuf.ar(1, buf, (rate * rateMod) * BufRateScale.kr(buf), 1, 0, loop: 1);"
        )
        src_stereo = "var srcStereo = Pan2.ar(src, 0);"
    else:
        src_line = (
            "var src = PlayBuf.ar(2, buf, (rate * rateMod) * BufRateScale.kr(buf), 1, 0, loop: 1);"
        )
        src_stereo = "var srcStereo = src;"

    # PitchShift windowSize must be > 0.01 typically; keep mild dispersion only.
    # Feedback amount stays a fixed (bounded) arg — only delay/drive wobble with chaos.
    body = f"""\
{_rand_mod_prefix()}\
			{src_line}
			{src_stereo}
			var local = LocalIn.ar(2);
			var delayMod = (delayTime * (1.0 + (LFNoise1.kr(0.35 + chaos) * chaos * 0.35))).clip(0.01, 0.45);
			var driveMod = (drive * (1.0 + (LFNoise1.kr(0.25 + chaos) * chaos * 0.2))).clip(0.5, 6.0);
			var delayed = DelayC.ar(local, 0.5, delayMod);
			var mixed = srcStereo + (delayed * feedback);
			var filtered = HPF.ar(LPF.ar(mixed, lpf), hpf);
			var shifted = PitchShift.ar(filtered, 0.2, 1.0, pitchDispersion, pitchDispersion * 0.5);
			var driven = (shifted * driveMod).tanh;
			var limited = Limiter.ar(driven, 0.9);
			LocalOut.ar(limited);
			Out.ar(out, Balance2.ar(limited[0], limited[1], panMod, ampMod) * 0.85);
"""

    time_offset = 0.05
    render_duration = duration + time_offset
    score_body = "\n".join(
        [
            "\t[0.0, ['/d_recv', SynthDef(\\remixero_feedback, {"
            " |out=0, buf=0, rate=1, delayTime=0.1, feedback=0.4, drive=1.5, lpf=8000, hpf=60, "
            "pitchDispersion=0, amp=0.85, pan=0, randDepth=0, randSeed=0|\n"
            f"{body}"
            "\t}).asBytes]],",
            f'\t[0.0, ["/b_allocRead", 0, "{in_path}"]],',
            (
                f"\t[{time_offset:.6f}, [\\s_new, \\remixero_feedback, 1000, 0, 0, "
                f"\\buf, 0, \\rate, {rate:.6f}, \\delayTime, {delay_time:.6f}, "
                f"\\feedback, {feedback:.6f}, \\drive, {drive:.6f}, "
                f"\\lpf, {lpf:.3f}, \\hpf, {hpf:.3f}, "
                f"\\pitchDispersion, {pitch_dispersion:.6f}, "
                f"\\amp, 0.85, \\pan, 0.0, "
                f"\\randDepth, {rand_d:.6f}, \\randSeed, {_sc_seed(params.seed)}]],"
            ),
            f"\t[{render_duration:.6f}, [\\c_set, 0, 0]]",
        ]
    )
    return _wrap_score(
        mode=params.mode,
        intensity=params.intensity,
        seed=params.seed,
        sample_rate=sample_rate,
        render_duration=render_duration,
        out_path=out_path,
        score_body=score_body,
        comment=(
            f"feedback={feedback:.3f} (max {max_feedback:.2f}) "
            f"delay={delay_time:.3f}s drive={drive:.2f}"
        ),
    )


def generate_comb_patch(
    *,
    params: RemixParameters,
    input_wav: Path,
    output_wav: Path,
) -> str:
    """Continuous comb/resonator color over looping buffer playback."""
    details = params.details
    delay_time = max(0.005, min(0.2, float(details["delay_time"])))
    decay = max(0.2, min(6.0, float(details["decay"])))
    wet = max(0.0, min(1.0, float(details["wet"])))
    rate = max(0.4, min(1.8, float(details.get("playback_rate") or 1.0)))
    hpf = max(20.0, min(2000.0, float(details.get("hpf") or 60.0)))
    lpf = max(200.0, min(18000.0, float(details.get("lpf") or 8000.0)))
    return _generate_continuous_layer_patch(
        params=params,
        input_wav=input_wav,
        output_wav=output_wav,
        synth_name="remixero_comb",
        arg_defaults=(
            "|out=0, buf=0, rate=1, delayTime=0.03, decay=1.5, wet=0.5, hpf=60, lpf=8000, "
            "amp=0.7, pan=0, attack=0.02, sustain=1.0, release=0.05, randDepth=0, randSeed=0|\n"
        ),
        body=_comb_synth_body(params.channels),
        start_args=(
            f"\\rate, {rate:.6f}, \\delayTime, {delay_time:.6f}, \\decay, {decay:.6f}, "
            f"\\wet, {wet:.6f}, \\hpf, {hpf:.3f}, \\lpf, {lpf:.3f}, "
            f"\\amp, 0.75, \\pan, 0.0, \\attack, 0.02, "
            f"\\sustain, {max(0.05, params.duration - 0.07):.6f}, \\release, 0.05, "
            f"\\randDepth, {_details_rand_depth(params.details, intensity=params.intensity):.6f}, "
            f"\\randSeed, {_sc_seed(params.seed)}"
        ),
        comment=f"comb delay={delay_time:.4f}s decay={decay:.2f} wet={wet:.2f}",
    )


def generate_ring_mod_patch(
    *,
    params: RemixParameters,
    input_wav: Path,
    output_wav: Path,
) -> str:
    """Ring-modulated looping buffer playback."""
    details = params.details
    mod_freq = max(20.0, min(2000.0, float(details["mod_freq"])))
    depth = max(0.0, min(1.0, float(details["depth"])))
    drive = max(0.5, min(4.0, float(details.get("drive") or 1.5)))
    rate = max(0.4, min(1.8, float(details.get("playback_rate") or 1.0)))
    lpf = max(200.0, min(18000.0, float(details.get("lpf") or 8000.0)))
    return _generate_continuous_layer_patch(
        params=params,
        input_wav=input_wav,
        output_wav=output_wav,
        synth_name="remixero_ringmod",
        arg_defaults=(
            "|out=0, buf=0, rate=1, modFreq=100, depth=0.8, drive=1.5, lpf=8000, "
            "amp=0.7, pan=0, attack=0.02, sustain=1.0, release=0.05, randDepth=0, randSeed=0|\n"
        ),
        body=_ring_mod_synth_body(params.channels),
        start_args=(
            f"\\rate, {rate:.6f}, \\modFreq, {mod_freq:.3f}, \\depth, {depth:.6f}, "
            f"\\drive, {drive:.6f}, \\lpf, {lpf:.3f}, "
            f"\\amp, 0.75, \\pan, 0.0, \\attack, 0.02, "
            f"\\sustain, {max(0.05, params.duration - 0.07):.6f}, \\release, 0.05, "
            f"\\randDepth, {_details_rand_depth(params.details, intensity=params.intensity):.6f}, "
            f"\\randSeed, {_sc_seed(params.seed)}"
        ),
        comment=f"ring_mod freq={mod_freq:.1f}Hz depth={depth:.2f}",
    )


def generate_pitch_warp_patch(
    *,
    params: RemixParameters,
    input_wav: Path,
    output_wav: Path,
) -> str:
    """Pitch-shifted / rate-warped looping buffer."""
    details = params.details
    pitch_ratio = max(0.25, min(2.5, float(details["pitch_ratio"])))
    pitch_dispersion = max(0.0, min(0.2, float(details.get("pitch_dispersion") or 0.0)))
    time_dispersion = max(0.0, min(0.2, float(details.get("time_dispersion") or 0.0)))
    rate = max(0.4, min(1.8, float(details.get("playback_rate") or 1.0)))
    drive = max(0.5, min(4.0, float(details.get("drive") or 1.5)))
    wet = max(0.0, min(1.0, float(details.get("wet") or 0.8)))
    return _generate_continuous_layer_patch(
        params=params,
        input_wav=input_wav,
        output_wav=output_wav,
        synth_name="remixero_pitchwarp",
        arg_defaults=(
            "|out=0, buf=0, rate=1, pitchRatio=1, pitchDispersion=0, timeDispersion=0, "
            "drive=1.5, wet=0.8, amp=0.7, pan=0, attack=0.02, sustain=1.0, release=0.05, "
            "randDepth=0, randSeed=0|\n"
        ),
        body=_pitch_warp_synth_body(params.channels),
        start_args=(
            f"\\rate, {rate:.6f}, \\pitchRatio, {pitch_ratio:.6f}, "
            f"\\pitchDispersion, {pitch_dispersion:.6f}, "
            f"\\timeDispersion, {time_dispersion:.6f}, "
            f"\\drive, {drive:.6f}, \\wet, {wet:.6f}, "
            f"\\amp, 0.75, \\pan, 0.0, \\attack, 0.02, "
            f"\\sustain, {max(0.05, params.duration - 0.07):.6f}, \\release, 0.05, "
            f"\\randDepth, {_details_rand_depth(params.details, intensity=params.intensity):.6f}, "
            f"\\randSeed, {_sc_seed(params.seed)}"
        ),
        comment=f"pitch_warp ratio={pitch_ratio:.3f} wet={wet:.2f}",
    )


def generate_pump_patch(
    *,
    params: RemixParameters,
    input_wav: Path,
    output_wav: Path,
) -> str:
    """Sidechain-style pump with transient emphasis."""
    details = params.details
    pump_rate = max(1.0, min(8.0, float(details["pump_rate"])))
    depth = max(0.0, min(0.95, float(details["depth"])))
    pulse_width = max(0.05, min(0.45, float(details.get("pulse_width") or 0.12)))
    transient_boost = max(0.0, min(1.0, float(details.get("transient_boost") or 0.4)))
    drive = max(0.5, min(4.0, float(details.get("drive") or 1.5)))
    rate = max(0.4, min(1.8, float(details.get("playback_rate") or 1.0)))
    hpf = max(20.0, min(2000.0, float(details.get("hpf") or 60.0)))
    lpf = max(200.0, min(18000.0, float(details.get("lpf") or 8000.0)))
    return _generate_continuous_layer_patch(
        params=params,
        input_wav=input_wav,
        output_wav=output_wav,
        synth_name="remixero_pump",
        arg_defaults=(
            "|out=0, buf=0, rate=1, pumpRate=2, depth=0.7, pulseWidth=0.12, "
            "transientBoost=0.4, drive=1.5, hpf=60, lpf=8000, "
            "amp=0.7, pan=0, attack=0.02, sustain=1.0, release=0.05, randDepth=0, randSeed=0|\n"
        ),
        body=_pump_synth_body(params.channels),
        start_args=(
            f"\\rate, {rate:.6f}, \\pumpRate, {pump_rate:.6f}, \\depth, {depth:.6f}, "
            f"\\pulseWidth, {pulse_width:.6f}, \\transientBoost, {transient_boost:.6f}, "
            f"\\drive, {drive:.6f}, \\hpf, {hpf:.3f}, \\lpf, {lpf:.3f}, "
            f"\\amp, 0.75, \\pan, 0.0, \\attack, 0.02, "
            f"\\sustain, {max(0.05, params.duration - 0.07):.6f}, \\release, 0.05, "
            f"\\randDepth, {_details_rand_depth(params.details, intensity=params.intensity):.6f}, "
            f"\\randSeed, {_sc_seed(params.seed)}"
        ),
        comment=f"pump rate={pump_rate:.2f}Hz depth={depth:.2f}",
    )


def _pump_synth_body(channels: int) -> str:
    src = _looping_src_lines_modulated(channels)
    return f"""\
{_rand_mod_prefix()}\
{src}
			var env = EnvGen.kr(Env.linen(attack, sustain, release), doneAction: 2);
			var pumpMod = (pumpRate * (1.0 + (LFNoise1.kr(0.2 + chaos) * chaos * 0.25))).clip(1.0, 8.0);
			var depthMod = (depth * (1.0 + (LFNoise1.kr(0.35) * chaos * 0.2))).clip(0.0, 0.95);
			var pulse = LFPulse.kr(pumpMod, 0, pulseWidth);
			var duck = Lag.kr(1.0 - (pulse * depthMod), 0.03);
			var filtered = HPF.ar(LPF.ar(srcStereo, lpf), hpf);
			var pumped = filtered * duck;
			var trans = HPF.ar(filtered, 1800) * transientBoost;
			var driven = ((pumped + trans) * drive).tanh;
			var limited = Limiter.ar(Balance2.ar(driven[0], driven[1], panMod, ampMod) * env, 0.95);
			Out.ar(out, limited);
"""


def generate_layered_patch(
    *,
    params: RemixParameters,
    input_wav: Path,
    output_wav: Path,
) -> str:
    """Mix multiple plan layers into one NRT Score with a shared buffer and master limiter."""
    layers = params.details.get("layers") or []
    if not isinstance(layers, list) or not layers:
        raise ValueError("layered parameters must include a non-empty layers list")

    in_path = escape_sc_string(str(input_wav.resolve()))
    out_path = escape_sc_string(str(output_wav.resolve()))
    channels = params.channels
    sample_rate = params.sample_rate
    duration = params.duration
    time_offset = 0.05
    mix_bus = 16  # private stereo bus for pre-limiter mix

    events: list[str] = []
    # SynthDefs used by any layer kind present.
    kinds = {str(layer.get("kind")) for layer in layers}
    events.extend(_layered_synthdefs(channels=channels, kinds=kinds, mix_bus=mix_bus))
    events.append(f'\t[0.0, ["/b_allocRead", 0, "{in_path}"]],')
    master = params.details.get("master") or {}
    drive = max(0.8, min(2.5, float(master.get("drive") or 1.2)))
    makeup = max(0.5, min(1.5, float(master.get("makeup") or 0.95)))
    # Soft energy-aware master: light drive + limiter (section energy baked into drive).
    section_energy = params.details.get("section_energy") or []
    if isinstance(section_energy, list) and section_energy:
        peak_energy = max(float(item.get("energy") or 0.5) for item in section_energy)
        drive = max(drive, 1.0 + peak_energy * 0.9)
        makeup = max(makeup, 0.8 + peak_energy * 0.15)
    events.append(
        "\t[0.0, ['/d_recv', SynthDef(\\remixero_master, {"
        f" |inBus={mix_bus}, out=0, drive={drive:.4f}, makeup={makeup:.4f}|\n"
        "\t\t\tvar sig = In.ar(inBus, 2);\n"
        "\t\t\tvar driven = (sig * drive).tanh;\n"
        "\t\t\tvar widened = driven + DelayC.ar(driven, 0.03, 0.012) * 0.12;\n"
        "\t\t\tOut.ar(out, Limiter.ar(widened * makeup, 0.95));\n"
        "\t}).asBytes]],"
    )
    events.append(
        f"\t[{time_offset:.6f}, [\\s_new, \\remixero_master, 900, 1, 0, "
        f"\\inBus, {mix_bus}, \\out, 0, \\drive, {drive:.4f}, \\makeup, {makeup:.4f}]],"
    )

    node_id = 1000
    latest = duration + time_offset
    for layer in layers:
        kind = str(layer.get("kind"))
        start = float(layer.get("start") or 0.0) + time_offset
        end = float(layer.get("end") or duration) + time_offset
        volume = max(0.0, min(2.0, float(layer.get("volume") or 1.0)))
        pan = max(-1.0, min(1.0, float(layer.get("pan") or 0.0)))
        details = layer.get("details") or {}
        if not isinstance(details, dict):
            details = {}
        fade_in = max(0.05, float(layer.get("fade_in") or 0.35))
        fade_out = max(0.05, float(layer.get("fade_out") or 0.35))
        total = max(0.08, end - start)
        # Env.linen(attack, sustain, release) must fit the play window.
        attack = min(fade_in, total * 0.45)
        release = min(fade_out, total * 0.45)
        sustain = max(0.02, total - attack - release)
        layer_rand = _details_rand_depth(
            details, intensity=float(layer.get("intensity") or params.intensity)
        )

        if kind == "grains":
            grain_events = layer.get("events") or details.get("grains") or []
            for item in grain_events:
                onset = float(item["onset"]) + time_offset
                latest = max(latest, onset + float(item["dur"]) + 0.05)
                node_id, line = _grain_event_line(
                    node_id=node_id,
                    onset=onset,
                    item=item,
                    sample_rate=sample_rate,
                    volume=volume,
                    out_bus=mix_bus,
                    rand_depth=layer_rand,
                    seed=params.seed,
                )
                events.append(line)
        elif kind == "fragments":
            fragment_events = layer.get("events") or details.get("events") or []
            feedback_amount = float(details.get("feedback_amount") or 0.0)
            feedback_amount = max(0.0, min(0.55, feedback_amount))
            for item in fragment_events:
                onset = float(item["onset"]) + time_offset
                latest = max(latest, onset + float(item["dur"]) + 0.05)
                node_id, line = _fragment_event_line(
                    node_id=node_id,
                    onset=onset,
                    item=item,
                    sample_rate=sample_rate,
                    volume=volume,
                    feedback_amount=feedback_amount,
                    out_bus=mix_bus,
                    rand_depth=layer_rand,
                    seed=params.seed,
                )
                events.append(line)
        elif kind == "feedback":
            latest = max(latest, end)
            fb = max(0.0, min(0.82, float(details.get("feedback") or 0.4)))
            delay_time = max(0.01, min(0.45, float(details.get("delay_time") or 0.1)))
            drive = max(0.5, min(6.0, float(details.get("drive") or 1.5)))
            lpf = max(200.0, min(18000.0, float(details.get("lpf") or 8000.0)))
            hpf = max(20.0, min(4000.0, float(details.get("hpf") or 60.0)))
            rate = max(0.5, min(1.5, float(details.get("playback_rate") or 1.0)))
            pitch_dispersion = max(
                0.0, min(0.2, float(details.get("pitch_dispersion") or 0.0))
            )
            events.append(
                f"\t[{start:.6f}, [\\s_new, \\remixero_feedback_layer, {node_id}, 0, 0, "
                f"\\out, {mix_bus}, \\buf, 0, \\rate, {rate:.6f}, "
                f"\\delayTime, {delay_time:.6f}, \\feedback, {fb:.6f}, "
                f"\\drive, {drive:.6f}, \\lpf, {lpf:.3f}, \\hpf, {hpf:.3f}, "
                f"\\pitchDispersion, {pitch_dispersion:.6f}, "
                f"\\amp, {volume:.6f}, \\pan, {pan:.6f}, "
                f"\\attack, {attack:.6f}, \\sustain, {sustain:.6f}, \\release, {release:.6f}, "
                f"\\randDepth, {layer_rand:.6f}, \\randSeed, {_sc_seed(params.seed ^ node_id)}]],"
            )
            node_id += 1
        elif kind == "comb":
            latest = max(latest, end)
            delay_time = max(0.005, min(0.2, float(details.get("delay_time") or 0.03)))
            decay = max(0.2, min(6.0, float(details.get("decay") or 1.5)))
            wet = max(0.0, min(1.0, float(details.get("wet") or 0.5)))
            rate = max(0.4, min(1.8, float(details.get("playback_rate") or 1.0)))
            hpf = max(20.0, min(2000.0, float(details.get("hpf") or 60.0)))
            lpf = max(200.0, min(18000.0, float(details.get("lpf") or 8000.0)))
            events.append(
                f"\t[{start:.6f}, [\\s_new, \\remixero_comb, {node_id}, 0, 0, "
                f"\\out, {mix_bus}, \\buf, 0, \\rate, {rate:.6f}, "
                f"\\delayTime, {delay_time:.6f}, \\decay, {decay:.6f}, \\wet, {wet:.6f}, "
                f"\\hpf, {hpf:.3f}, \\lpf, {lpf:.3f}, "
                f"\\amp, {volume:.6f}, \\pan, {pan:.6f}, "
                f"\\attack, {attack:.6f}, \\sustain, {sustain:.6f}, \\release, {release:.6f}, "
                f"\\randDepth, {layer_rand:.6f}, \\randSeed, {_sc_seed(params.seed ^ node_id)}]],"
            )
            node_id += 1
        elif kind == "ring_mod":
            latest = max(latest, end)
            mod_freq = max(20.0, min(2000.0, float(details.get("mod_freq") or 100.0)))
            depth = max(0.0, min(1.0, float(details.get("depth") or 0.8)))
            drive = max(0.5, min(4.0, float(details.get("drive") or 1.5)))
            rate = max(0.4, min(1.8, float(details.get("playback_rate") or 1.0)))
            lpf = max(200.0, min(18000.0, float(details.get("lpf") or 8000.0)))
            events.append(
                f"\t[{start:.6f}, [\\s_new, \\remixero_ringmod, {node_id}, 0, 0, "
                f"\\out, {mix_bus}, \\buf, 0, \\rate, {rate:.6f}, "
                f"\\modFreq, {mod_freq:.3f}, \\depth, {depth:.6f}, \\drive, {drive:.6f}, "
                f"\\lpf, {lpf:.3f}, \\amp, {volume:.6f}, \\pan, {pan:.6f}, "
                f"\\attack, {attack:.6f}, \\sustain, {sustain:.6f}, \\release, {release:.6f}, "
                f"\\randDepth, {layer_rand:.6f}, \\randSeed, {_sc_seed(params.seed ^ node_id)}]],"
            )
            node_id += 1
        elif kind == "pitch_warp":
            latest = max(latest, end)
            pitch_ratio = max(0.25, min(2.5, float(details.get("pitch_ratio") or 1.0)))
            pitch_dispersion = max(
                0.0, min(0.2, float(details.get("pitch_dispersion") or 0.0))
            )
            time_dispersion = max(
                0.0, min(0.2, float(details.get("time_dispersion") or 0.0))
            )
            rate = max(0.4, min(1.8, float(details.get("playback_rate") or 1.0)))
            drive = max(0.5, min(4.0, float(details.get("drive") or 1.5)))
            wet = max(0.0, min(1.0, float(details.get("wet") or 0.8)))
            events.append(
                f"\t[{start:.6f}, [\\s_new, \\remixero_pitchwarp, {node_id}, 0, 0, "
                f"\\out, {mix_bus}, \\buf, 0, \\rate, {rate:.6f}, "
                f"\\pitchRatio, {pitch_ratio:.6f}, \\pitchDispersion, {pitch_dispersion:.6f}, "
                f"\\timeDispersion, {time_dispersion:.6f}, \\drive, {drive:.6f}, "
                f"\\wet, {wet:.6f}, \\amp, {volume:.6f}, \\pan, {pan:.6f}, "
                f"\\attack, {attack:.6f}, \\sustain, {sustain:.6f}, \\release, {release:.6f}, "
                f"\\randDepth, {layer_rand:.6f}, \\randSeed, {_sc_seed(params.seed ^ node_id)}]],"
            )
            node_id += 1
        elif kind == "pump":
            latest = max(latest, end)
            pump_rate = max(1.0, min(8.0, float(details.get("pump_rate") or 2.0)))
            depth = max(0.0, min(0.95, float(details.get("depth") or 0.7)))
            pulse_width = max(
                0.05, min(0.45, float(details.get("pulse_width") or 0.12))
            )
            transient_boost = max(
                0.0, min(1.0, float(details.get("transient_boost") or 0.4))
            )
            drive = max(0.5, min(4.0, float(details.get("drive") or 1.5)))
            rate = max(0.4, min(1.8, float(details.get("playback_rate") or 1.0)))
            hpf = max(20.0, min(2000.0, float(details.get("hpf") or 60.0)))
            lpf = max(200.0, min(18000.0, float(details.get("lpf") or 8000.0)))
            events.append(
                f"\t[{start:.6f}, [\\s_new, \\remixero_pump, {node_id}, 0, 0, "
                f"\\out, {mix_bus}, \\buf, 0, \\rate, {rate:.6f}, "
                f"\\pumpRate, {pump_rate:.6f}, \\depth, {depth:.6f}, "
                f"\\pulseWidth, {pulse_width:.6f}, \\transientBoost, {transient_boost:.6f}, "
                f"\\drive, {drive:.6f}, \\hpf, {hpf:.3f}, \\lpf, {lpf:.3f}, "
                f"\\amp, {volume:.6f}, \\pan, {pan:.6f}, "
                f"\\attack, {attack:.6f}, \\sustain, {sustain:.6f}, \\release, {release:.6f}, "
                f"\\randDepth, {layer_rand:.6f}, \\randSeed, {_sc_seed(params.seed ^ node_id)}]],"
            )
            node_id += 1
        elif kind == "passthrough":
            latest = max(latest, end)
            events.append(
                f"\t[{start:.6f}, [\\s_new, \\remixero_passthrough_layer, {node_id}, 0, 0, "
                f"\\out, {mix_bus}, \\buf, 0, \\rate, 1.0, "
                f"\\amp, {volume:.6f}, \\pan, {pan:.6f}, "
                f"\\attack, {attack:.6f}, \\sustain, {sustain:.6f}, \\release, {release:.6f}]],"
            )
            node_id += 1
        else:
            raise ValueError(f"Unsupported layered kind '{kind}'")

    render_duration = latest + 0.05
    events.append(f"\t[{render_duration:.6f}, [\\c_set, 0, 0]]")
    layer_summary = ", ".join(
        f"{layer.get('id')}:{layer.get('kind')}" for layer in layers
    )
    return _wrap_score(
        mode=params.mode,
        intensity=params.intensity,
        seed=params.seed,
        sample_rate=sample_rate,
        render_duration=render_duration,
        out_path=out_path,
        score_body="\n".join(events),
        comment=f"layered ({len(layers)}): {layer_summary}",
    )


def _generate_continuous_layer_patch(
    *,
    params: RemixParameters,
    input_wav: Path,
    output_wav: Path,
    synth_name: str,
    arg_defaults: str,
    body: str,
    start_args: str,
    comment: str,
) -> str:
    in_path = escape_sc_string(str(input_wav.resolve()))
    out_path = escape_sc_string(str(output_wav.resolve()))
    time_offset = 0.05
    render_duration = params.duration + time_offset
    score_body = "\n".join(
        [
            f"\t[0.0, ['/d_recv', SynthDef(\\{synth_name}, {{"
            f" {arg_defaults}"
            f"{body}"
            "\t}).asBytes]],",
            f'\t[0.0, ["/b_allocRead", 0, "{in_path}"]],',
            (
                f"\t[{time_offset:.6f}, [\\s_new, \\{synth_name}, 1000, 0, 0, "
                f"\\buf, 0, {start_args}]],"
            ),
            f"\t[{render_duration:.6f}, [\\c_set, 0, 0]]",
        ]
    )
    return _wrap_score(
        mode=params.mode,
        intensity=params.intensity,
        seed=params.seed,
        sample_rate=params.sample_rate,
        render_duration=render_duration,
        out_path=out_path,
        score_body=score_body,
        comment=comment,
    )


def _comb_synth_body(channels: int) -> str:
    src = _looping_src_lines_modulated(channels)
    return f"""\
{_rand_mod_prefix()}\
{src}
			var env = EnvGen.kr(Env.linen(attack, sustain, release), doneAction: 2);
			var delayMod = (delayTime * (1.0 + (LFNoise1.kr(0.4 + chaos) * chaos * 0.4))).clip(0.005, 0.2);
			var decayMod = (decay * (1.0 + (LFNoise1.kr(0.3 + chaos) * chaos * 0.35))).clip(0.2, 6.0);
			var filtered = HPF.ar(LPF.ar(srcStereo, lpf), hpf);
			var reson = CombC.ar(filtered, 0.25, delayMod, decayMod);
			var mixed = (filtered * (1.0 - wet)) + (reson * wet);
			var limited = Limiter.ar(Balance2.ar(mixed[0], mixed[1], panMod, ampMod) * env, 0.95);
			Out.ar(out, limited);
"""


def _ring_mod_synth_body(channels: int) -> str:
    src = _looping_src_lines_modulated(channels)
    return f"""\
{_rand_mod_prefix()}\
{src}
			var env = EnvGen.kr(Env.linen(attack, sustain, release), doneAction: 2);
			var freqMod = (modFreq * (1.0 + (LFNoise1.kr(0.6 + chaos * 2) * chaos * 0.5))).clip(20, 2000);
			var jumpFreq = freqMod * (1.0 + ((TRand.kr(0.7, 1.4, dustTrig) - 1.0) * chaos));
			var carrier = SinOsc.ar(jumpFreq);
			var modulated = srcStereo * ((1.0 - depth) + (carrier * depth));
			var driven = (LPF.ar(modulated, lpf) * drive).tanh;
			var limited = Limiter.ar(Balance2.ar(driven[0], driven[1], panMod, ampMod) * env, 0.95);
			Out.ar(out, limited);
"""


def _pitch_warp_synth_body(channels: int) -> str:
    src = _looping_src_lines_modulated(channels)
    return f"""\
{_rand_mod_prefix()}\
{src}
			var env = EnvGen.kr(Env.linen(attack, sustain, release), doneAction: 2);
			var ratioMod = (pitchRatio * (1.0 + (LFNoise1.kr(0.45 + chaos) * chaos * 0.35))).clip(0.25, 2.5);
			var dispMod = (pitchDispersion + (LFNoise1.kr(0.8) * chaos * 0.08)).clip(0, 0.25);
			var shifted = PitchShift.ar(srcStereo, 0.2, ratioMod, dispMod, timeDispersion);
			var mixed = (srcStereo * (1.0 - wet)) + (shifted * wet);
			var driven = (mixed * drive).tanh;
			var limited = Limiter.ar(Balance2.ar(driven[0], driven[1], panMod, ampMod) * env, 0.95);
			Out.ar(out, limited);
"""


def _looping_src_lines(channels: int) -> str:
    if channels == 1:
        return (
            "\t\t\tvar src = PlayBuf.ar(1, buf, rate * BufRateScale.kr(buf), 1, 0, loop: 1);\n"
            "\t\t\tvar srcStereo = Pan2.ar(src, 0);"
        )
    return (
        "\t\t\tvar src = PlayBuf.ar(2, buf, rate * BufRateScale.kr(buf), 1, 0, loop: 1);\n"
        "\t\t\tvar srcStereo = src;"
    )


def _looping_src_lines_modulated(channels: int) -> str:
    """Looping PlayBuf using rateMod from ``_rand_mod_prefix``."""
    if channels == 1:
        return (
            "\t\t\tvar src = PlayBuf.ar(1, buf, (rate * rateMod) * BufRateScale.kr(buf), 1, 0, loop: 1);\n"
            "\t\t\tvar srcStereo = Pan2.ar(src, 0);"
        )
    return (
        "\t\t\tvar src = PlayBuf.ar(2, buf, (rate * rateMod) * BufRateScale.kr(buf), 1, 0, loop: 1);\n"
        "\t\t\tvar srcStereo = src;"
    )


def _layered_synthdefs(*, channels: int, kinds: set[str], mix_bus: int) -> list[str]:
    del mix_bus  # master uses explicit bus arg
    defs: list[str] = []
    if "grains" in kinds:
        play = _grain_play_lines(channels)
        defs.append(
            "\t[0.0, ['/d_recv', SynthDef(\\remixero_grain, {"
            " |out=0, buf=0, startPos=0, rate=1, attack=0.005, sustain=0.05, release=0.02, "
            "amp=0.2, pan=0, randDepth=0, randSeed=0|\n"
            f"{play}\n"
            "\t}).asBytes]],"
        )
    if "fragments" in kinds:
        play = _fragment_play_lines(channels)
        defs.append(
            "\t[0.0, ['/d_recv', SynthDef(\\remixero_fragment, {"
            " |out=0, buf=0, startPos=0, rate=1, attack=0.002, sustain=0.05, release=0.01, "
            "amp=0.2, pan=0, distort=0, lpf=12000, hpf=40, feedbackAmt=0, "
            "randDepth=0, randSeed=0|\n"
            f"{play}\n"
            "\t}).asBytes]],"
        )
    if "feedback" in kinds:
        body = _feedback_layer_body(channels)
        defs.append(
            "\t[0.0, ['/d_recv', SynthDef(\\remixero_feedback_layer, {"
            " |out=0, buf=0, rate=1, delayTime=0.1, feedback=0.4, drive=1.5, lpf=8000, hpf=60, "
            "pitchDispersion=0, amp=0.7, pan=0, attack=0.02, sustain=1.0, release=0.05, "
            "randDepth=0, randSeed=0|\n"
            f"{body}"
            "\t}).asBytes]],"
        )
    if "comb" in kinds:
        defs.append(
            "\t[0.0, ['/d_recv', SynthDef(\\remixero_comb, {"
            " |out=0, buf=0, rate=1, delayTime=0.03, decay=1.5, wet=0.5, hpf=60, lpf=8000, "
            "amp=0.7, pan=0, attack=0.02, sustain=1.0, release=0.05, randDepth=0, randSeed=0|\n"
            f"{_comb_synth_body(channels)}"
            "\t}).asBytes]],"
        )
    if "ring_mod" in kinds:
        defs.append(
            "\t[0.0, ['/d_recv', SynthDef(\\remixero_ringmod, {"
            " |out=0, buf=0, rate=1, modFreq=100, depth=0.8, drive=1.5, lpf=8000, "
            "amp=0.7, pan=0, attack=0.02, sustain=1.0, release=0.05, randDepth=0, randSeed=0|\n"
            f"{_ring_mod_synth_body(channels)}"
            "\t}).asBytes]],"
        )
    if "pitch_warp" in kinds:
        defs.append(
            "\t[0.0, ['/d_recv', SynthDef(\\remixero_pitchwarp, {"
            " |out=0, buf=0, rate=1, pitchRatio=1, pitchDispersion=0, timeDispersion=0, "
            "drive=1.5, wet=0.8, amp=0.7, pan=0, attack=0.02, sustain=1.0, release=0.05, "
            "randDepth=0, randSeed=0|\n"
            f"{_pitch_warp_synth_body(channels)}"
            "\t}).asBytes]],"
        )
    if "pump" in kinds:
        defs.append(
            "\t[0.0, ['/d_recv', SynthDef(\\remixero_pump, {"
            " |out=0, buf=0, rate=1, pumpRate=2, depth=0.7, pulseWidth=0.12, "
            "transientBoost=0.4, drive=1.5, hpf=60, lpf=8000, "
            "amp=0.7, pan=0, attack=0.02, sustain=1.0, release=0.05, randDepth=0, randSeed=0|\n"
            f"{_pump_synth_body(channels)}"
            "\t}).asBytes]],"
        )
    if "passthrough" in kinds:
        src = _looping_src_lines(channels)
        defs.append(
            "\t[0.0, ['/d_recv', SynthDef(\\remixero_passthrough_layer, {"
            " |out=0, buf=0, rate=1, amp=0.7, pan=0, attack=0.02, sustain=1.0, release=0.05|\n"
            f"{src}\n"
            "\t\t\tvar env = EnvGen.kr(Env.linen(attack, sustain, release), doneAction: 2);\n"
            "\t\t\tvar limited = Limiter.ar(Balance2.ar(srcStereo[0], srcStereo[1], pan, amp) * env, 0.95);\n"
            "\t\t\tOut.ar(out, limited);\n"
            "\t}).asBytes]],"
        )
    return defs


def _grain_play_lines(channels: int) -> str:
    if channels == 1:
        return (
            f"{_rand_mod_prefix_light()}"
            "\t\t\tvar playRate = rate * rateMod;\n"
            "\t\t\tvar sig = PlayBuf.ar(1, buf, playRate * BufRateScale.kr(buf), 1, startPos, loop: 0);\n"
            "\t\t\tvar env = EnvGen.kr(Env.linen(attack, sustain, release), doneAction: 2);\n"
            "\t\t\tvar limited = Limiter.ar(Pan2.ar(sig, panMod, ampMod) * env, 0.95);\n"
            "\t\t\tOut.ar(out, limited);"
        )
    return (
        f"{_rand_mod_prefix_light()}"
        "\t\t\tvar playRate = rate * rateMod;\n"
        "\t\t\tvar sig = PlayBuf.ar(2, buf, playRate * BufRateScale.kr(buf), 1, startPos, loop: 0);\n"
        "\t\t\tvar env = EnvGen.kr(Env.linen(attack, sustain, release), doneAction: 2);\n"
        "\t\t\tvar limited = Limiter.ar(Balance2.ar(sig[0], sig[1], panMod, ampMod) * env, 0.95);\n"
        "\t\t\tOut.ar(out, limited);"
    )


def _fragment_play_lines(channels: int) -> str:
    if channels == 1:
        read_sig = (
            "PlayBuf.ar(1, buf, (rate * rateMod) "
            "* BufRateScale.kr(buf), 1, startPos, loop: 0)"
        )
        spatialize = "Pan2.ar(sig, panMod, ampMod)"
    else:
        read_sig = (
            "PlayBuf.ar(2, buf, (rate * rateMod) "
            "* BufRateScale.kr(buf), 1, startPos, loop: 0)"
        )
        spatialize = "Balance2.ar(sig[0], sig[1], panMod, ampMod)"
    return f"""\
{_rand_mod_prefix_light()}\
			var dry = {read_sig};
			var env = EnvGen.kr(Env.linen(attack, sustain, release), doneAction: 2);
			var lpfMod = (lpf * (1.0 + (LFNoise1.kr(0.7 + chaos) * chaos * 0.35))).clip(200, 18000);
			var hpfMod = (hpf * (1.0 + (LFNoise1.kr(0.5 + chaos) * chaos * 0.25))).clip(20, 4000);
			var shaped = HPF.ar(LPF.ar(dry, lpfMod), hpfMod);
			var driven = (shaped * (1.0 + (distort * 8.0))).tanh;
			var sig = driven;
			var wet = DelayC.ar(sig, 0.3, 0.12) * feedbackAmt;
			var mixed = ({spatialize} + Pan2.ar(wet, panMod * 0.5, ampMod * 0.5)) * env;
			var limited = Limiter.ar(mixed, 0.95);
			Out.ar(out, limited);"""


def _feedback_layer_body(channels: int) -> str:
    if channels == 1:
        src_line = (
            "var src = PlayBuf.ar(1, buf, (rate * rateMod) * BufRateScale.kr(buf), 1, 0, loop: 1);"
        )
        src_stereo = "var srcStereo = Pan2.ar(src, 0);"
    else:
        src_line = (
            "var src = PlayBuf.ar(2, buf, (rate * rateMod) * BufRateScale.kr(buf), 1, 0, loop: 1);"
        )
        src_stereo = "var srcStereo = src;"
    return f"""\
{_rand_mod_prefix()}\
			{src_line}
			{src_stereo}
			var env = EnvGen.kr(Env.linen(attack, sustain, release), doneAction: 2);
			var local = LocalIn.ar(2);
			var delayMod = (delayTime * (1.0 + (LFNoise1.kr(0.35 + chaos) * chaos * 0.35))).clip(0.01, 0.45);
			var driveMod = (drive * (1.0 + (LFNoise1.kr(0.25 + chaos) * chaos * 0.2))).clip(0.5, 6.0);
			var delayed = DelayC.ar(local, 0.5, delayMod);
			var mixed = srcStereo + (delayed * feedback);
			var filtered = HPF.ar(LPF.ar(mixed, lpf), hpf);
			var shifted = PitchShift.ar(filtered, 0.2, 1.0, pitchDispersion, pitchDispersion * 0.5);
			var driven = (shifted * driveMod).tanh;
			var limited = Limiter.ar(driven, 0.9);
			LocalOut.ar(limited);
			Out.ar(out, Balance2.ar(limited[0], limited[1], panMod, ampMod) * env * 0.85);
"""


def _grain_event_line(
    *,
    node_id: int,
    onset: float,
    item: dict,
    sample_rate: int,
    volume: float,
    out_bus: int,
    rand_depth: float = 0.0,
    seed: int = 0,
) -> tuple[int, str]:
    dur = float(item["dur"])
    attack = min(0.01, dur * 0.2)
    release = min(0.03, dur * 0.3)
    sustain = max(0.005, dur - attack - release)
    amp = float(item["amp"]) * volume
    start_samples = int(round(float(item["buf_pos"]) * sample_rate))
    grain_seed = _sc_seed(seed ^ node_id)
    line = (
        f"\t[{onset:.6f}, [\\s_new, \\remixero_grain, {node_id}, 0, 0, "
        f"\\out, {out_bus}, \\buf, 0, \\startPos, {start_samples}, "
        f"\\rate, {float(item['rate']):.6f}, "
        f"\\attack, {attack:.6f}, \\sustain, {sustain:.6f}, \\release, {release:.6f}, "
        f"\\amp, {amp:.6f}, \\pan, {float(item['pan']):.6f}, "
        f"\\randDepth, {rand_depth:.6f}, \\randSeed, {grain_seed}]],"
    )
    return node_id + 1, line


def _fragment_event_line(
    *,
    node_id: int,
    onset: float,
    item: dict,
    sample_rate: int,
    volume: float,
    feedback_amount: float,
    out_bus: int,
    rand_depth: float = 0.0,
    seed: int = 0,
) -> tuple[int, str]:
    dur = float(item["dur"])
    attack = min(0.008, dur * 0.15)
    release = min(0.025, dur * 0.25)
    sustain = max(0.004, dur - attack - release)
    amp = float(item["amp"]) * volume
    start_samples = int(round(float(item["buf_pos"]) * sample_rate))
    frag_seed = _sc_seed(seed ^ node_id)
    line = (
        f"\t[{onset:.6f}, [\\s_new, \\remixero_fragment, {node_id}, 0, 0, "
        f"\\out, {out_bus}, \\buf, 0, \\startPos, {start_samples}, "
        f"\\rate, {float(item['rate']):.6f}, "
        f"\\attack, {attack:.6f}, \\sustain, {sustain:.6f}, \\release, {release:.6f}, "
        f"\\amp, {amp:.6f}, \\pan, {float(item['pan']):.6f}, "
        f"\\distort, {float(item.get('distort', 0.0)):.6f}, "
        f"\\lpf, {float(item.get('lpf', 12000.0)):.3f}, "
        f"\\hpf, {float(item.get('hpf', 40.0)):.3f}, "
        f"\\feedbackAmt, {feedback_amount:.6f}, "
        f"\\randDepth, {rand_depth:.6f}, \\randSeed, {frag_seed}]],"
    )
    return node_id + 1, line


def _wrap_score(
    *,
    mode: str,
    intensity: float,
    seed: int,
    sample_rate: int,
    render_duration: float,
    out_path: str,
    score_body: str,
    comment: str = "",
) -> str:
    extra = f"\n// {comment}" if comment else ""
    seeded = "\n".join(_rand_seed_score_events(seed))
    return f"""\
// Remixero {mode} render
// mode={mode} intensity={intensity:.3f} seed={seed}{extra}
// Generated for inspection; safe to edit manually.
(
var server, score, duration, sampleRate;
duration = {render_duration:.6f};
sampleRate = {sample_rate};

server = Server(
	\\remixero_nrt,
	options: ServerOptions.new
		.numOutputBusChannels_(2)
		.numInputBusChannels_(2)
		.sampleRate_(sampleRate)
);

score = Score([
{seeded}
{score_body}
]);

score.recordNRT(
	outputFilePath: "{out_path}",
	sampleRate: sampleRate,
	headerFormat: "WAV",
	sampleFormat: "int16",
	options: server.options,
	duration: duration,
	action: {{
		server.remove;
		0.exit;
	}}
);
)
"""
