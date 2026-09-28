"""Terminal presentation helpers."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from noise_remix import __version__
from noise_remix.models.analysis import AudioAnalysis, AudioProbe
from noise_remix.models.environment import EnvironmentInfo

console = Console(stderr=False)


def print_banner() -> None:
    console.print(f"[bold]Remixero[/bold] [dim]{__version__}[/dim]")


def print_environment(env: EnvironmentInfo) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("SuperCollider", f"{env.supercollider_version} ({env.sclang_path})")
    table.add_row("scsynth", env.scsynth_path)
    ffmpeg_label = env.ffmpeg_version or env.ffmpeg_path
    table.add_row("FFmpeg", ffmpeg_label)
    console.print(Panel(table, title="Environment", expand=False))


def print_probe(probe: AudioProbe) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Source", probe.path)
    table.add_row("Duration", _format_duration(probe.duration))
    table.add_row("Sample rate", f"{probe.sample_rate} Hz")
    table.add_row("Channels", str(probe.channels))
    table.add_row("Format", probe.format_name)
    if probe.codec_name:
        table.add_row("Codec", probe.codec_name)
    console.print(Panel(table, title="Source", expand=False))


def print_analysis(analysis: AudioAnalysis) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Transients", str(len(analysis.transients)))
    bpm = (
        f"~{analysis.estimated_bpm}"
        if analysis.estimated_bpm is not None
        else "n/a (approx only)"
    )
    table.add_row("Estimated BPM", bpm)
    table.add_row(
        "Spectral flux",
        f"{analysis.spectral_flux:.2f} ({analysis.spectral_flux_label})",
    )
    table.add_row(
        "Dynamic range",
        f"{analysis.dynamic_range_db:.1f} dB ({analysis.dynamic_range_label})",
    )
    table.add_row("Segments", str(len(analysis.segments)))
    table.add_row("Centroid", f"{analysis.spectral_centroid_hz:.0f} Hz")
    console.print(Panel(table, title="Analysis", expand=False))


def print_step(message: str, *, ok: bool = True) -> None:
    mark = "[green]✓[/green]" if ok else "[cyan]→[/cyan]"
    console.print(f"{mark} {message}")


def print_success(
    *,
    outputs: list[Path],
    seeds: list[int],
    patch: Path | None = None,
) -> None:
    console.print()
    console.print("[bold green]Render complete[/bold green]")
    if len(outputs) == 1:
        console.print(f"Output:  {outputs[0]}")
        console.print(f"Seed:    {seeds[0]}")
    else:
        console.print("Outputs:")
        for path, seed in zip(outputs, seeds, strict=True):
            console.print(f"  {path}  (seed {seed})")
    if patch is not None:
        console.print(f"Patch:   {patch}")


def print_error(message: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {message}")


def prompt_mode(choices: list[str]) -> str:
    """Simple terminal mode selection (no full-screen TUI)."""
    from rich.prompt import Prompt

    console.print()
    console.print("[bold]Select remix mode:[/bold]")
    for index, name in enumerate(choices, start=1):
        console.print(f"  {index}. {name}")
    console.print()
    while True:
        raw = Prompt.ask("Selection", default="1")
        if raw.strip().lower() in choices:
            return raw.strip().lower()
        try:
            selected = int(raw)
        except ValueError:
            console.print("[yellow]Enter a number or mode name.[/yellow]")
            continue
        if 1 <= selected <= len(choices):
            return choices[selected - 1]
        console.print("[yellow]Invalid selection.[/yellow]")


def prompt_intensity(default: float = 0.5) -> float:
    from rich.prompt import FloatPrompt

    while True:
        value = FloatPrompt.ask("Intensity (0.0-1.0)", default=default)
        if 0.0 <= value <= 1.0:
            return value
        console.print("[yellow]Intensity must be between 0.0 and 1.0.[/yellow]")


def prompt_instruction() -> str:
    from rich.prompt import Prompt

    console.print()
    console.print("Describe what you want to do with this recording:")
    while True:
        value = Prompt.ask(">")
        if value.strip():
            return value.strip()
        console.print("[yellow]Instruction cannot be empty.[/yellow]")


def print_production_plan(plan, *, instruction: str) -> None:
    from noise_remix.models.production import ProductionPlan

    assert isinstance(plan, ProductionPlan)
    console.print()
    console.print("[bold]AI PRODUCTION PLAN[/bold]")
    console.print("────────────────────────────────────────────")
    console.print()
    console.print("[bold]Instruction:[/bold]")
    console.print(f"  {instruction}")
    console.print()
    console.print("[bold]Concept:[/bold]")
    console.print(f"  {plan.title}")
    console.print(f"  {plan.description}")
    if plan.narrative:
        console.print(f"  {plan.narrative}")
    console.print()
    console.print("[bold]Structure:[/bold]")
    for section in plan.sections:
        console.print(
            f"  {_format_duration(section.start)}–{_format_duration(section.end)}  "
            f"{section.name} (energy {section.energy:.2f})"
        )
        if section.description:
            console.print(f"    {section.description}")
    console.print()
    console.print("[bold]Layers:[/bold]")
    for index, layer in enumerate(plan.layers, start=1):
        span = (
            f"{_format_duration(layer.start)}–"
            f"{_format_duration(layer.end) if layer.end is not None else 'end'}"
        )
        console.print(
            f"  {index}. {layer.id} [{layer.processor}] "
            f"intensity={layer.intensity:.2f} vol={layer.volume:.2f} {span}"
        )
    console.print()
    console.print(
        f"Primary mode: {plan.global_parameters.primary_mode}  "
        f"overall intensity: {plan.global_parameters.overall_intensity:.2f}"
    )
    console.print(f"Duration: {_format_duration(plan.duration_seconds)}")


def confirm_render(default_yes: bool = True) -> bool:
    from rich.prompt import Confirm

    return Confirm.ask("Render?", default=default_yes)


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    fraction = seconds - total
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        base = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        base = f"{minutes:02d}:{secs:02d}"
    if fraction > 0.001 and total < 60:
        return f"{seconds:.2f}s ({base})"
    return base
