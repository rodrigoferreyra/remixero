"""CLI commands."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Optional

import typer

from noise_remix import __version__
from noise_remix.audio.analysis import analyze_audio
from noise_remix.audio.conversion import convert_to_wav
from noise_remix.audio.input import validate_input
from noise_remix.cli import display
from noise_remix.errors import InputError, RemixeroError
from noise_remix.hashing import hash_file
from noise_remix.models.production import plan_summary_dict
from noise_remix.output.manager import allocate_output_paths, ensure_output_dir
from noise_remix.output.metadata import build_metadata, write_analysis, write_metadata
from noise_remix.remix import available_modes, get_mode
from noise_remix.seed import resolve_seed, variation_seed
from noise_remix.supercollider.environment import discover_environment
from noise_remix.supercollider.generator import generate_patch
from noise_remix.supercollider.renderer import render_patch

app = typer.Typer(
    name="remixero",
    help="Procedural noise remix tool powered by SuperCollider.",
    add_completion=False,
    no_args_is_help=True,
)

_INTERACTIVE_MODES = ["granular", "destroy", "collapse", "feedback", "random"]


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"remixero {__version__}")
        raise typer.Exit()


@app.command()
def main(
    input_file: Path = typer.Argument(
        ...,
        metavar="INPUT",
        help="Source audio file (mp3, wav, flac, ogg).",
    ),
    mode: Optional[str] = typer.Option(
        None,
        "--mode",
        "-m",
        help="Remix mode. If omitted in a TTY (non-AI), prompts interactively.",
    ),
    intensity: Optional[float] = typer.Option(
        None,
        "--intensity",
        "-i",
        help="Transformation intensity in [0.0, 1.0]. Default 0.5 (or prompted in TTY).",
    ),
    variations: int = typer.Option(
        1,
        "--variations",
        help="Number of variations to render.",
    ),
    seed: str = typer.Option(
        "random",
        "--seed",
        help="Integer seed or 'random'.",
    ),
    output: Path = typer.Option(
        Path("output"),
        "--output",
        "-o",
        help="Output directory.",
        show_default=True,
    ),
    duration: Optional[float] = typer.Option(
        None,
        "--duration",
        help="Max source/render duration in seconds (default: full source; smoke caps at 5s).",
    ),
    preview: Optional[float] = typer.Option(
        None,
        "--preview",
        help="Fast preview: analyze/render only the first N seconds (e.g. --preview 15).",
    ),
    keep_patch: bool = typer.Option(
        False,
        "--keep-patch",
        help="Retain the generated SuperCollider .scd next to the WAV.",
    ),
    keep_analysis: bool = typer.Option(
        False,
        "--keep-analysis",
        help="Write analysis JSON next to outputs.",
    ),
    ai: bool = typer.Option(
        False,
        "--ai",
        help="Enable AI creative-director mode (Gemini or Groq).",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="AI provider: gemini or groq (default: auto from env/config/keys).",
    ),
    prompt: Optional[str] = typer.Option(
        None,
        "--prompt",
        "--instruction",
        help="Natural-language creative instruction (implies --ai).",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip render confirmation in AI mode.",
    ),
    keep_plan: bool = typer.Option(
        False,
        "--keep-plan",
        help="Write the validated AI production plan JSON next to outputs.",
    ),
    hybrid_listen: bool = typer.Option(
        False,
        "--hybrid-listen",
        help=(
            "With --provider groq: run a Gemini audio-listen pass first "
            "(requires GEMINI_API_KEY), then plan with Groq."
        ),
    ),
    plan_only: bool = typer.Option(
        False,
        "--plan-only",
        help="Generate and print an AI production plan without rendering.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show additional diagnostic detail.",
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Analyze input and render a procedural SuperCollider remix."""
    try:
        _run(
            input_file=input_file,
            mode=mode,
            intensity=intensity,
            variations=variations,
            seed_value=seed,
            output_dir=output,
            duration=duration,
            preview=preview,
            keep_patch=keep_patch,
            keep_analysis=keep_analysis,
            ai=ai or prompt is not None or plan_only,
            provider=provider,
            prompt=prompt,
            yes=yes,
            keep_plan=keep_plan,
            hybrid_listen=hybrid_listen,
            plan_only=plan_only,
            verbose=verbose,
        )
    except RemixeroError as exc:
        display.print_error(str(exc))
        raise typer.Exit(code=1) from exc
    except KeyError as exc:
        display.print_error(str(exc))
        raise typer.Exit(code=1) from exc


def _run(
    *,
    input_file: Path,
    mode: str | None,
    intensity: float | None,
    variations: int,
    seed_value: str,
    output_dir: Path,
    duration: float | None,
    preview: float | None,
    keep_patch: bool,
    keep_analysis: bool,
    ai: bool,
    provider: str | None,
    prompt: str | None,
    yes: bool,
    keep_plan: bool,
    hybrid_listen: bool,
    plan_only: bool,
    verbose: bool,
) -> None:
    if variations < 1:
        raise InputError("--variations must be >= 1.")
    if preview is not None and preview <= 0:
        raise InputError("--preview must be greater than 0.")
    # Preview is a convenience cap on duration.
    if preview is not None:
        duration = preview if duration is None else min(duration, preview)

    if ai:
        _run_ai(
            input_file=input_file,
            intensity=intensity,
            variations=variations,
            seed_value=seed_value,
            output_dir=output_dir,
            duration=duration,
            preview=preview,
            keep_patch=keep_patch,
            keep_analysis=keep_analysis,
            provider=provider,
            prompt=prompt,
            yes=yes,
            keep_plan=keep_plan,
            hybrid_listen=hybrid_listen,
            plan_only=plan_only,
            verbose=verbose,
        )
        return

    interactive = mode is None and sys.stdin.isatty()
    if mode is None:
        mode_name = (
            display.prompt_mode(_INTERACTIVE_MODES) if interactive else "granular"
        )
    else:
        mode_name = mode.strip().lower()

    if intensity is None:
        intensity_value = display.prompt_intensity(0.5) if interactive else 0.5
    else:
        intensity_value = intensity
    if not 0.0 <= intensity_value <= 1.0:
        raise InputError("--intensity must be between 0.0 and 1.0.")

    try:
        remix_mode = get_mode(mode_name)
    except KeyError as exc:
        raise InputError(
            f"Unknown mode '{mode_name}'. Available: {', '.join(available_modes())}"
        ) from exc

    base_seed = resolve_seed(seed_value)
    display.print_banner()

    env = discover_environment()
    display.print_step("Environment validated")
    if verbose:
        display.print_environment(env)

    probe = validate_input(input_file)
    display.print_step("Input validated")
    display.print_probe(probe)

    source_hash = hash_file(Path(probe.path))
    analysis_duration = _resolve_analysis_duration(
        probe.duration, duration, mode=mode_name
    )
    if preview is not None:
        display.print_step(
            f"Preview mode — using first {analysis_duration:.1f}s of source"
        )

    outputs: list[Path] = []
    seeds: list[int] = []
    last_patch: Path | None = None

    with tempfile.TemporaryDirectory(prefix="remixero-") as tmp:
        tmp_dir = Path(tmp)
        work_wav = tmp_dir / "source.wav"
        display.print_step("Preparing analysis/render copy", ok=False)
        convert_to_wav(
            Path(probe.path),
            work_wav,
            sample_rate=probe.sample_rate,
            channels=probe.channels,
            max_duration=analysis_duration,
        )
        display.print_step("Render copy ready")

        analysis = analyze_audio(work_wav)
        display.print_step(
            f"Audio analyzed — {len(analysis.segments)} source segments identified"
        )
        display.print_analysis(analysis)

        if keep_analysis:
            _write_analysis_file(output_dir, input_file.stem, analysis)

        for variation_index in range(variations):
            var_seed = (
                base_seed
                if variations == 1
                else variation_seed(base_seed, variation_index)
            )
            params = remix_mode.generate(
                analysis=analysis,
                intensity=intensity_value,
                seed=var_seed,
                duration=analysis.duration,
            )
            display.print_step(
                "Remix configuration generated "
                f"(mode={mode_name}, variation {variation_index + 1}/{variations}, seed {var_seed})"
            )

            wav_path, meta_path, patch_path = allocate_output_paths(
                output_dir=output_dir,
                source_stem=input_file.stem,
                mode=mode_name,
                index=variation_index + 1,
                keep_patch=keep_patch,
            )
            _render_one(
                tmp_dir=tmp_dir,
                variation_index=variation_index,
                work_wav=work_wav,
                wav_path=wav_path,
                meta_path=meta_path,
                patch_path=patch_path,
                params=params,
                input_name=input_file.name,
                source_hash=source_hash,
                analysis=analysis,
                env=env,
                plan_summary=None,
            )
            outputs.append(wav_path)
            seeds.append(var_seed)
            last_patch = patch_path

    display.print_success(
        outputs=outputs,
        seeds=seeds,
        patch=last_patch if variations == 1 else None,
    )


def _run_ai(
    *,
    input_file: Path,
    intensity: float | None,
    variations: int,
    seed_value: str,
    output_dir: Path,
    duration: float | None,
    preview: float | None,
    keep_patch: bool,
    keep_analysis: bool,
    provider: str | None,
    prompt: str | None,
    yes: bool,
    keep_plan: bool,
    hybrid_listen: bool,
    plan_only: bool,
    verbose: bool,
) -> None:
    from noise_remix.ai.config import load_ai_config
    from noise_remix.ai.director import generate_production_plan
    from noise_remix.ai.executor import plan_to_remix_parameters

    instruction = prompt
    if not instruction:
        if sys.stdin.isatty():
            instruction = display.prompt_instruction()
        else:
            raise InputError(
                "AI mode requires --prompt/--instruction, or a TTY to ask for one."
            )

    if intensity is not None and not 0.0 <= intensity <= 1.0:
        raise InputError("--intensity must be between 0.0 and 1.0.")

    ai_config = load_ai_config(provider_override=provider)
    base_seed = resolve_seed(seed_value)
    display.print_banner()

    env = discover_environment()
    display.print_step("Environment validated")
    if verbose:
        display.print_environment(env)
    display.print_step(f"AI provider={ai_config.provider} model={ai_config.model}")
    if ai_config.provider == "groq":
        from noise_remix.ai.config import gemini_api_key_available

        if hybrid_listen and gemini_api_key_available():
            display.print_step(
                "Hybrid listen on: Gemini will listen; Groq will build the plan"
            )
        elif hybrid_listen and not gemini_api_key_available():
            display.print_step(
                "Hybrid listen requested but no GEMINI_API_KEY — using analysis only",
                ok=False,
            )
        else:
            display.print_step(
                "Groq uses local analysis only (pass --hybrid-listen for Gemini listen)",
                ok=True,
            )

    probe = validate_input(input_file)
    display.print_step("Input validated")
    display.print_probe(probe)

    source_hash = hash_file(Path(probe.path))
    analysis_duration = _resolve_analysis_duration(
        probe.duration, duration, mode="granular"
    )
    if preview is not None:
        display.print_step(
            f"Preview mode — using first {analysis_duration:.1f}s of source"
        )

    outputs: list[Path] = []
    seeds: list[int] = []
    last_patch: Path | None = None

    with tempfile.TemporaryDirectory(prefix="remixero-") as tmp:
        tmp_dir = Path(tmp)
        work_wav = tmp_dir / "source.wav"
        display.print_step("Preparing analysis/render copy", ok=False)
        convert_to_wav(
            Path(probe.path),
            work_wav,
            sample_rate=probe.sample_rate,
            channels=probe.channels,
            max_duration=analysis_duration,
        )
        display.print_step("Render copy ready")

        analysis = analyze_audio(work_wav)
        display.print_step(
            f"Audio analyzed — {len(analysis.segments)} source segments identified"
        )
        display.print_analysis(analysis)

        if keep_analysis:
            _write_analysis_file(output_dir, input_file.stem, analysis)

        for variation_index in range(variations):
            var_seed = (
                base_seed
                if variations == 1
                else variation_seed(base_seed, variation_index)
            )
            display.print_step(
                f"Requesting {ai_config.provider} production plan "
                f"(variation {variation_index + 1}/{variations})...",
                ok=False,
            )
            plan = generate_production_plan(
                audio_path=work_wav,
                analysis=analysis,
                instruction=instruction,
                duration_seconds=analysis.duration,
                config=ai_config,
                variation_index=variation_index,
                variations=variations,
                hybrid_listen=hybrid_listen,
                status=lambda message: display.print_step(message, ok=False),
            )
            if intensity is not None:
                plan.global_parameters.overall_intensity = intensity

            from noise_remix.ai.timing import align_plan_to_analysis

            # Snap sections to musical grid and attach crossfades before preview/save.
            plan = align_plan_to_analysis(plan, analysis)

            display.print_production_plan(plan, instruction=instruction)

            if keep_plan or plan_only:
                ensure_output_dir(output_dir)
                plan_path = _allocate_plan_path(
                    output_dir, input_file.stem, variation_index + 1
                )
                plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
                display.print_step(f"Production plan saved: {plan_path}")

            if plan_only:
                continue

            if not yes:
                if sys.stdin.isatty():
                    if not display.confirm_render(default_yes=True):
                        display.print_step("Render skipped")
                        continue
                else:
                    raise InputError(
                        "AI render confirmation required. Re-run with --yes for unattended mode."
                    )

            params = plan_to_remix_parameters(plan, analysis=analysis, seed=var_seed)
            mode_name = params.mode
            layer_count = len(params.details.get("layers") or [])
            if params.details.get("engine") == "layered" and layer_count:
                display.print_step(
                    f"Executing layered plan ({layer_count} voices) "
                    f"intensity={params.intensity:.2f} seed={var_seed}"
                )
            else:
                display.print_step(
                    f"Executing plan via mode={mode_name} "
                    f"intensity={params.intensity:.2f} seed={var_seed}"
                )

            wav_path, meta_path, patch_path = allocate_output_paths(
                output_dir=output_dir,
                source_stem=input_file.stem,
                mode=f"ai-{mode_name}",
                index=variation_index + 1,
                keep_patch=keep_patch,
            )
            _render_one(
                tmp_dir=tmp_dir,
                variation_index=variation_index,
                work_wav=work_wav,
                wav_path=wav_path,
                meta_path=meta_path,
                patch_path=patch_path,
                params=params,
                input_name=input_file.name,
                source_hash=source_hash,
                analysis=analysis,
                env=env,
                plan_summary=plan_summary_dict(plan),
            )
            outputs.append(wav_path)
            seeds.append(var_seed)
            last_patch = patch_path

    if outputs:
        display.print_success(
            outputs=outputs,
            seeds=seeds,
            patch=last_patch if len(outputs) == 1 else None,
        )
    elif plan_only:
        display.print_step("Plan-only complete (no render)")


def _render_one(
    *,
    tmp_dir: Path,
    variation_index: int,
    work_wav: Path,
    wav_path: Path,
    meta_path: Path,
    patch_path: Path | None,
    params,
    input_name: str,
    source_hash: str,
    analysis,
    env,
    plan_summary: dict | None,
) -> None:
    sc_text = generate_patch(
        params=params,
        input_wav=work_wav,
        output_wav=wav_path,
    )
    scd_write_path = (
        patch_path if patch_path is not None else tmp_dir / f"var-{variation_index}.scd"
    )
    scd_write_path.write_text(sc_text, encoding="utf-8")
    display.print_step("SuperCollider patch generated")
    display.print_step("Rendering...", ok=False)
    render_patch(
        patch_path=scd_write_path,
        output_wav=wav_path,
        env_info=env,
    )
    metadata = build_metadata(
        source_name=input_name,
        source_hash=source_hash,
        params=params,
        analysis=analysis,
        supercollider_version=env.supercollider_version,
        plan_summary=plan_summary,
    )
    write_metadata(meta_path, metadata)
    display.print_step(f"Render complete → {wav_path.name}")


def _write_analysis_file(output_dir: Path, stem: str, analysis) -> None:
    ensure_output_dir(output_dir)
    analysis_path = output_dir / f"{stem}-analysis.json"
    if analysis_path.exists():
        idx = 1
        while True:
            candidate = output_dir / f"{stem}-analysis-{idx:03d}.json"
            if not candidate.exists():
                analysis_path = candidate
                break
            idx += 1
    write_analysis(analysis_path, analysis)
    display.print_step(f"Analysis saved: {analysis_path}")


def _allocate_plan_path(output_dir: Path, stem: str, index: int) -> Path:
    path = output_dir / f"{stem}-ai-{index:03d}-plan.json"
    if not path.exists():
        return path
    n = index
    while True:
        candidate = output_dir / f"{stem}-ai-{n:03d}-plan.json"
        if not candidate.exists():
            return candidate
        n += 1


def _resolve_analysis_duration(
    source_duration: float,
    requested: float | None,
    *,
    mode: str,
) -> float:
    if requested is not None:
        if requested <= 0:
            raise InputError("--duration must be greater than 0.")
        return min(requested, source_duration)
    if mode == "smoke":
        return min(source_duration, 5.0)
    return source_duration
