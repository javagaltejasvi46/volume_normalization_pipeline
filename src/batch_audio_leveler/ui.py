"""Rich terminal UI rendering and interactive components."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.ffmpeg.discovery import FFmpegEnvironment
from batch_audio_leveler.models import FileJob, JobResult, NormalizationMode
from batch_audio_leveler.utils.paths import format_path_for_display

console = Console()


def render_banner(env: FFmpegEnvironment, config: AppConfig, queue_size: int) -> None:
    """Render application header and system summary panel."""
    ffmpeg_status = (
        f"[green]FFmpeg {env.ffmpeg.version}[/green]"
        if env.ffmpeg.available
        else "[red]FFmpeg NOT FOUND[/red]"
    )
    ffprobe_status = (
        f"[green]FFprobe {env.ffprobe.version}[/green]"
        if env.ffprobe.available
        else "[red]FFprobe NOT FOUND[/red]"
    )

    mode_desc = (
        "Batch Median"
        if config.mode == NormalizationMode.BATCH_MEDIAN
        else f"Fixed ({config.fixed_target_lufs:.1f} LUFS)"
    )

    header_text = Text()
    header_text.append("BATCH MP4 AUDIO LOUDNESS NORMALIZER\n", style="bold cyan")
    header_text.append(f"Tools: {ffmpeg_status} | {ffprobe_status}\n")
    header_text.append(
        f"Queue: [yellow]{queue_size} file(s)[/yellow] | Mode: [bold]{mode_desc}[/bold] | "
        f"Peak Ceiling: [bold]{config.true_peak_ceiling_dbtp:.1f} dBTP[/bold]\n"
    )
    header_text.append(f"Output Dir: [magenta]{format_path_for_display(config.output_dir, 60)}[/magenta]")

    console.print(Panel(header_text, box=box.ROUNDED, expand=False))


def render_main_menu() -> None:
    """Print the numbered main menu options."""
    menu_table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    menu_table.add_column("Key", style="bold green", width=4)
    menu_table.add_column("Action", style="white")

    menu_table.add_row("1", "Add MP4 file(s)")
    menu_table.add_row("2", "Add folder")
    menu_table.add_row("3", "Review / remove queued files")
    menu_table.add_row("4", "Configure normalization settings")
    menu_table.add_row("5", "Analyze batch (Pass 1)")
    menu_table.add_row("6", "Preview normalization plan")
    menu_table.add_row("7", "Process batch (Pass 2 + Verification)")
    menu_table.add_row("8", "View results & export reports")
    menu_table.add_row("9", "Change output directory")
    menu_table.add_row("0", "Exit")

    console.print(menu_table)


def render_queue_table(jobs: List[FileJob]) -> None:
    """Display the queued files table."""
    if not jobs:
        console.print("[yellow]The queue is currently empty.[/yellow]\n")
        return

    table = Table(title="Queued Files", box=box.ROUNDED)
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Filename", style="bold white")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Audio Streams", justify="center")
    table.add_column("Status", style="yellow")

    for i, job in enumerate(jobs, 1):
        filename = job.path.name
        dur_str = "--"
        streams_str = "--"
        if job.probe_result:
            if job.probe_result.duration_seconds:
                mins = int(job.probe_result.duration_seconds // 60)
                secs = int(job.probe_result.duration_seconds % 60)
                dur_str = f"{mins}m {secs}s"
            streams_str = str(len(job.probe_result.audio_streams))

        status_str = "Queued"
        if job.result:
            status_str = job.result.status.value.capitalize()
        elif job.measurement:
            status_str = "Analyzed"

        table.add_row(str(i), filename, dur_str, streams_str, status_str)

    console.print(table)


def render_plan_table(jobs: List[FileJob], target_lufs: float) -> None:
    """Display normalization preview table."""
    table = Table(
        title=f"Normalization Plan Preview (Batch Target: {target_lufs:.1f} LUFS)",
        box=box.ROUNDED,
    )
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Filename", style="bold white")
    table.add_column("Input LUFS", justify="right")
    table.add_column("Input TP", justify="right")
    table.add_column("Nominal Gain", justify="right")
    table.add_column("Effective Gain", justify="right")
    table.add_column("Mode", justify="center")
    table.add_column("Est. Output TP", justify="right")
    table.add_column("Warnings / Status", style="yellow")

    for i, job in enumerate(jobs, 1):
        m = job.measurement
        plan = job.plan
        fname = job.path.name

        if not m or not plan:
            table.add_row(str(i), fname, "--", "--", "--", "--", "--", "--", "[yellow]Not analyzed[/yellow]")
            continue

        in_lufs = f"{m.integrated_lufs:.1f}" if m.integrated_lufs is not None else "--"
        in_tp = f"{m.true_peak_dbtp:+.1f}" if m.true_peak_dbtp is not None else "--"
        nom_gain = f"{plan.requested_gain_db:+.1f} dB"
        eff_gain = f"{plan.effective_gain_db:+.1f} dB" if plan.effective_gain_db is not None else "--"
        mode_str = f"[bold green]{plan.planned_mode}[/bold green]" if plan.planned_mode == "linear" else f"[bold magenta]{plan.planned_mode}[/bold magenta]"
        est_tp = f"{plan.estimated_output_peak_dbtp:+.1f} dBTP" if plan.estimated_output_peak_dbtp is not None else "--"

        warn_text = "; ".join(plan.warnings) if plan.warnings else "[green]OK[/green]"
        table.add_row(str(i), fname, in_lufs, in_tp, nom_gain, eff_gain, mode_str, est_tp, warn_text)

    console.print(table)


def render_results_table(results: List[JobResult]) -> None:
    """Display final results and verification table."""
    table = Table(title="Normalization Batch Results", box=box.ROUNDED)
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Filename", style="bold white")
    table.add_column("Status", justify="center")
    table.add_column("Before LUFS", justify="right")
    table.add_column("After LUFS", justify="right")
    table.add_column("Before TP", justify="right")
    table.add_column("After TP", justify="right")
    table.add_column("Time (s)", justify="right")
    table.add_column("Notes", style="yellow")

    for i, res in enumerate(results, 1):
        fname = res.source_path.name
        status_color = "green" if res.status.value in {"verified", "completed"} else "red"
        status_str = f"[{status_color}]{res.status.value.upper()}[/{status_color}]"

        b_lufs = f"{res.before_measurement.integrated_lufs:.1f}" if (res.before_measurement and res.before_measurement.integrated_lufs is not None) else "--"
        a_lufs = f"{res.after_measurement.integrated_lufs:.1f}" if (res.after_measurement and res.after_measurement.integrated_lufs is not None) else "--"
        b_tp = f"{res.before_measurement.true_peak_dbtp:+.1f}" if (res.before_measurement and res.before_measurement.true_peak_dbtp is not None) else "--"
        a_tp = f"{res.after_measurement.true_peak_dbtp:+.1f}" if (res.after_measurement and res.after_measurement.true_peak_dbtp is not None) else "--"

        sec_str = f"{res.processing_seconds:.1f}" if res.processing_seconds is not None else "--"
        notes = res.error_message or ("; ".join(res.warnings) if res.warnings else "[green]Verified[/green]")

        table.add_row(str(i), fname, status_str, b_lufs, a_lufs, b_tp, a_tp, sec_str, notes)

    console.print(table)
