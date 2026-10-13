"""Typer CLI entry point and interactive session controller."""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import typer
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, FloatPrompt, Prompt

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.ffmpeg.analyzer import measure_file_loudness
from batch_audio_leveler.ffmpeg.discovery import discover_ffmpeg
from batch_audio_leveler.ffmpeg.probe import probe_file
from batch_audio_leveler.ffmpeg.processor import process_file_normalization
from batch_audio_leveler.ffmpeg.verifier import verify_normalized_file
from batch_audio_leveler.models import (
    FileJob,
    JobResult,
    JobStatus,
    NormalizationMode,
)
from batch_audio_leveler.normalization.planner import plan_file_normalization
from batch_audio_leveler.normalization.targets import calculate_batch_target
from batch_audio_leveler.queue_manager import QueueManager
from batch_audio_leveler.reporting.csv_report import export_csv_report
from batch_audio_leveler.reporting.json_report import export_json_report
from batch_audio_leveler.reporting.logging_setup import setup_logger
from batch_audio_leveler.ui import (
    console,
    render_banner,
    render_main_menu,
    render_plan_table,
    render_queue_table,
    render_results_table,
)
from batch_audio_leveler.utils.cancellation import CancellationToken
from batch_audio_leveler.utils.paths import (
    clean_path,
    ensure_directory,
    get_unique_output_path,
)

app = typer.Typer(
    name="batch-audio-leveler",
    help="MP4 Audio Loudness Normalizer using EBU R128 / ITU-R BS.1770",
    add_completion=False,
)


class InteractiveSession:
    """Manages state and interactive commands in the terminal."""

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or AppConfig()
        self.queue = QueueManager()
        self.env = discover_ffmpeg(self.config.ffmpeg_path, self.config.ffprobe_path)
        if self.env.ffmpeg.available:
            self.config.ffmpeg_path = self.env.ffmpeg.path
        if self.env.ffprobe.available:
            self.config.ffprobe_path = self.env.ffprobe.path

        log_path = self.config.output_dir / "batch_audio_leveler.log"
        self.logger = setup_logger(log_path)
        self.results: List[JobResult] = []

    def run(self) -> None:
        """Main interaction loop."""
        while True:
            console.clear()
            render_banner(self.env, self.config, len(self.queue))
            render_main_menu()

            choice = Prompt.ask("\nSelect an option", default="0").strip()

            if choice == "1":
                self.action_add_files()
            elif choice == "2":
                self.action_add_folder()
            elif choice == "3":
                self.action_review_queue()
            elif choice == "4":
                self.action_configure_settings()
            elif choice == "5":
                self.action_analyze_batch()
            elif choice == "6":
                self.action_preview_plan()
            elif choice == "7":
                self.action_process_batch()
            elif choice == "8":
                self.action_view_results()
            elif choice == "9":
                self.action_change_output_dir()
            elif choice == "0":
                console.print("[cyan]Exiting Batch Audio Leveler. Goodbye![/cyan]")
                break
            else:
                console.print("[red]Invalid selection. Press Enter to continue.[/red]")
                Prompt.ask("")

    def action_add_files(self) -> None:
        raw = Prompt.ask("\nEnter MP4 file path(s) (supports drag-and-drop or space/semicolon separated)")
        if not raw.strip():
            return

        # Handle multiple paths separated by quotes or semicolons
        paths = [p.strip() for p in raw.split(";") if p.strip()]
        if len(paths) == 1 and not raw.strip().endswith(".mp4"):
            paths = [raw.strip()]

        added = 0
        for p_str in paths:
            job = self.queue.add_file(p_str)
            if job:
                added += 1
                if self.env.ffprobe.available and not job.probe_result:
                    try:
                        job.probe_result = probe_file(job.path, self.env.ffprobe.path)
                    except Exception:
                        pass

        console.print(f"[green]Added {added} file(s) to queue.[/green]")
        time.sleep(1.2)

    def action_add_folder(self) -> None:
        raw_folder = Prompt.ask("\nEnter folder path to scan")
        folder = clean_path(raw_folder)
        if not folder.is_dir():
            console.print(f"[red]Folder '{folder}' does not exist.[/red]")
            time.sleep(1.5)
            return

        recursive = Confirm.ask("Include subfolders recursively?", default=self.config.include_subfolders)
        added = self.queue.add_folder(folder, recursive=recursive)

        # Probe newly added items
        if self.env.ffprobe.available:
            for job in self.queue.jobs:
                if not job.probe_result:
                    try:
                        job.probe_result = probe_file(job.path, self.env.ffprobe.path)
                    except Exception:
                        pass

        console.print(f"[green]Added {added} MP4 file(s) from '{folder.name}'.[/green]")
        time.sleep(1.2)

    def action_review_queue(self) -> None:
        while True:
            console.clear()
            render_queue_table(self.queue.jobs)
            console.print("[cyan]Options: [R]emove an item | [C]lear queue | [B]ack[/cyan]")
            sub = Prompt.ask("Action", default="B").strip().upper()
            if sub == "B":
                break
            elif sub == "C":
                if Confirm.ask("Are you sure you want to clear the queue?", default=False):
                    self.queue.clear()
                    self.results.clear()
                    console.print("[yellow]Queue cleared.[/yellow]")
                    time.sleep(1)
                    break
            elif sub == "R":
                idx_str = Prompt.ask("Enter item number to remove")
                if idx_str.isdigit():
                    idx = int(idx_str) - 1
                    if self.queue.remove_index(idx):
                        console.print(f"[green]Removed item #{idx_str}.[/green]")
                    else:
                        console.print("[red]Invalid item number.[/red]")
                    time.sleep(1)

    def action_configure_settings(self) -> None:
        while True:
            console.clear()
            console.print(f"[bold cyan]CONFIGURATION & SETTINGS[/bold cyan]\n")
            mode_name = "Batch Median" if self.config.mode == NormalizationMode.BATCH_MEDIAN else "Fixed Target"
            console.print(f"1. Mode: [yellow]{mode_name}[/yellow]")
            console.print(f"2. Fixed Target LUFS: [yellow]{self.config.fixed_target_lufs:.1f} LUFS[/yellow]")
            console.print(f"3. True Peak Ceiling: [yellow]{self.config.true_peak_ceiling_dbtp:.1f} dBTP[/yellow]")
            console.print(f"4. Audio Bitrate: [yellow]{self.config.audio_bitrate}[/yellow]")
            console.print(f"5. Allow Dynamic Mode: [yellow]{self.config.allow_dynamic}[/yellow]")
            console.print(f"6. Max Gain-Up Limit: [yellow]+{self.config.max_gain_up_db:.1f} dB[/yellow]")
            console.print(f"7. Max Gain-Down Limit: [yellow]{self.config.max_gain_down_db:.1f} dB[/yellow]")
            console.print(f"8. Target LRA: [yellow]{self.config.target_lra:.1f} LU[/yellow]")
            console.print("0. Back to Main Menu")

            opt = Prompt.ask("\nSelect setting to adjust", default="0").strip()
            if opt == "0":
                break
            elif opt == "1":
                is_fixed = Confirm.ask("Use Fixed Target mode instead of Batch Median?", default=(self.config.mode == NormalizationMode.FIXED))
                self.config.mode = NormalizationMode.FIXED if is_fixed else NormalizationMode.BATCH_MEDIAN
            elif opt == "2":
                self.config.fixed_target_lufs = FloatPrompt.ask("Enter Target LUFS (e.g. -16.0)", default=self.config.fixed_target_lufs)
            elif opt == "3":
                self.config.true_peak_ceiling_dbtp = FloatPrompt.ask("Enter True Peak Ceiling dBTP (e.g. -2.0)", default=self.config.true_peak_ceiling_dbtp)
            elif opt == "4":
                self.config.audio_bitrate = Prompt.ask("Enter Audio Bitrate (e.g. 192k, 256k)", default=self.config.audio_bitrate)
            elif opt == "5":
                self.config.allow_dynamic = Confirm.ask("Allow dynamic compression when linear gain hits peak ceiling?", default=self.config.allow_dynamic)
            elif opt == "6":
                self.config.max_gain_up_db = FloatPrompt.ask("Enter Max Gain-Up Limit (dB)", default=self.config.max_gain_up_db)
            elif opt == "7":
                self.config.max_gain_down_db = FloatPrompt.ask("Enter Max Gain-Down Limit (negative dB)", default=self.config.max_gain_down_db)
            elif opt == "8":
                self.config.target_lra = FloatPrompt.ask("Enter Target LRA (LU)", default=self.config.target_lra)

    def action_change_output_dir(self) -> None:
        raw = Prompt.ask("\nEnter new output directory path", default=str(self.config.output_dir))
        try:
            target_dir = ensure_directory(Path(raw))
            self.config.output_dir = target_dir
            console.print(f"[green]Output directory set to '{target_dir}'.[/green]")
        except Exception as e:
            console.print(f"[red]Failed to set directory: {e}[/red]")
        time.sleep(1.5)

    def action_analyze_batch(self) -> None:
        if not self.env.ffmpeg.available:
            console.print(f"[red]Cannot analyze: FFmpeg is not available.\n{self.env.ffmpeg.error_message}[/red]")
            Prompt.ask("\nPress Enter to continue")
            return

        jobs = self.queue.jobs
        if not jobs:
            console.print("[yellow]Queue is empty. Add files first.[/yellow]")
            time.sleep(1.5)
            return

        console.print(f"\n[cyan]Starting Pass 1: Loudness Analysis for {len(jobs)} file(s)...[/cyan]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing...", total=len(jobs))

            with CancellationToken() as cancel_token:
                for job in jobs:
                    if cancel_token.is_cancelled:
                        console.print("[yellow]Analysis interrupted by user.[/yellow]")
                        break

                    progress.update(task, description=f"Analyzing {job.path.name}...")
                    try:
                        m = measure_file_loudness(
                            file_path=job.path,
                            ffmpeg_path=self.config.ffmpeg_path,
                            stream_index=job.selected_stream_index,
                            target_i=self.config.fixed_target_lufs,
                            target_tp=self.config.true_peak_ceiling_dbtp,
                            target_lra=self.config.target_lra,
                            timeout_seconds=self.config.timeout_seconds,
                            cancellation_token=cancel_token,
                        )
                        job.measurement = m
                    except Exception as e:
                        console.print(f"[red]Error analyzing '{job.path.name}': {e}[/red]")

                    progress.advance(task)

        console.print("\n[green]Analysis complete![/green]")
        Prompt.ask("Press Enter to continue")

    def action_preview_plan(self) -> None:
        jobs = self.queue.jobs
        if not jobs:
            console.print("[yellow]Queue is empty.[/yellow]")
            time.sleep(1.5)
            return

        # Check if all files have measurements
        missing = [j for j in jobs if not j.measurement]
        if missing:
            console.print(f"[yellow]{len(missing)} file(s) have not been analyzed yet. Run 'Analyze batch' first.[/yellow]")
            Prompt.ask("Press Enter to continue")
            return

        measurements = [j.measurement for j in jobs if j.measurement]
        try:
            target_lufs = calculate_batch_target(measurements, self.config)
        except Exception as e:
            console.print(f"[red]Error calculating batch target: {e}[/red]")
            Prompt.ask("Press Enter to continue")
            return

        # Generate plans
        for job in jobs:
            if job.measurement:
                job.plan = plan_file_normalization(job.measurement, target_lufs, self.config)

        console.clear()
        render_plan_table(jobs, target_lufs)
        Prompt.ask("\nPress Enter to return to main menu")

    def action_process_batch(self) -> None:
        if not self.env.ffmpeg.available:
            console.print(f"[red]Cannot process: FFmpeg is not available.\n{self.env.ffmpeg.error_message}[/red]")
            Prompt.ask("\nPress Enter to continue")
            return

        jobs = self.queue.jobs
        if not jobs:
            console.print("[yellow]Queue is empty.[/yellow]")
            time.sleep(1.5)
            return

        # Ensure analysis and plans exist
        unmeasured = [j for j in jobs if not j.measurement]
        if unmeasured:
            console.print("[yellow]Analyzing queued files first...[/yellow]")
            self.action_analyze_batch()

        measurements = [j.measurement for j in jobs if j.measurement]
        try:
            target_lufs = calculate_batch_target(measurements, self.config)
        except Exception as e:
            console.print(f"[red]Cannot process batch: {e}[/red]")
            Prompt.ask("Press Enter to continue")
            return

        for job in jobs:
            if job.measurement:
                job.plan = plan_file_normalization(job.measurement, target_lufs, self.config)

        console.clear()
        render_plan_table(jobs, target_lufs)
        if not Confirm.ask("\nProceed with normalization?", default=True):
            return

        ensure_directory(self.config.output_dir)
        self.results.clear()

        console.print(f"\n[cyan]Normalizing and verifying {len(jobs)} file(s)...[/cyan]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing...", total=len(jobs))

            with CancellationToken() as cancel_token:
                for job in jobs:
                    if cancel_token.is_cancelled:
                        console.print("[yellow]Processing cancelled by user.[/yellow]")
                        break

                    start_time = time.time()
                    now_str = datetime.now(timezone.utc).isoformat()
                    final_out = get_unique_output_path(
                        self.config.output_dir,
                        job.path,
                        overwrite=self.config.overwrite_existing,
                    )

                    res = JobResult(
                        source_path=job.path,
                        output_path=final_out,
                        status=JobStatus.PROCESSING,
                        before_measurement=job.measurement,
                        plan=job.plan,
                        started_at=now_str,
                    )
                    job.result = res

                    progress.update(task, description=f"Normalizing {job.path.name}...")

                    # Skip silent or invalid plans
                    if not job.plan or job.plan.planned_mode == "skip":
                        res.status = JobStatus.SKIPPED
                        res.warnings.append("Skipped due to silent or unmeasurable audio.")
                        res.finished_at = datetime.now(timezone.utc).isoformat()
                        res.processing_seconds = time.time() - start_time
                        self.results.append(res)
                        progress.advance(task)
                        continue

                    try:
                        # Pass 2: Normalize to temp file
                        temp_out = process_file_normalization(
                            input_path=job.path,
                            final_output_path=final_out,
                            plan=job.plan,
                            measurement=job.measurement,
                            config=self.config,
                            stream_index=job.selected_stream_index,
                            has_subtitles=(job.probe_result.has_subtitles if job.probe_result else False),
                            cancellation_token=cancel_token,
                        )

                        progress.update(task, description=f"Verifying {job.path.name}...")
                        # Pass 3: Verification
                        after_m, verify_warns = verify_normalized_file(
                            output_path=temp_out,
                            plan=job.plan,
                            config=self.config,
                            stream_index=job.selected_stream_index,
                            cancellation_token=cancel_token,
                        )

                        # Atomic rename to final output
                        if final_out.exists() and self.config.overwrite_existing:
                            final_out.unlink()
                        temp_out.rename(final_out)

                        res.after_measurement = after_m
                        res.warnings.extend(verify_warns)
                        res.status = JobStatus.VERIFIED
                        res.finished_at = datetime.now(timezone.utc).isoformat()
                        res.processing_seconds = time.time() - start_time

                    except Exception as e:
                        res.status = JobStatus.FAILED
                        res.error_message = str(e)
                        res.finished_at = datetime.now(timezone.utc).isoformat()
                        res.processing_seconds = time.time() - start_time
                        self.logger.error(f"Error processing {job.path.name}: {e}")

                    self.results.append(res)
                    progress.advance(task)

        # Auto-export reports
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = self.config.output_dir / f"batch_report_{timestamp}.csv"
        json_file = self.config.output_dir / f"batch_report_{timestamp}.json"
        export_csv_report(self.results, csv_file)
        export_json_report(self.results, json_file)

        console.print(f"\n[green]Processing complete! Exported reports to:[/green]")
        console.print(f"  CSV:  [bold]{csv_file.name}[/bold]")
        console.print(f"  JSON: [bold]{json_file.name}[/bold]\n")

        render_results_table(self.results)
        Prompt.ask("\nPress Enter to continue")

    def action_view_results(self) -> None:
        if not self.results:
            console.print("[yellow]No batch processing results yet.[/yellow]")
            time.sleep(1.5)
            return

        console.clear()
        render_results_table(self.results)

        # Option to retry failed items
        failed = [r for r in self.results if r.status == JobStatus.FAILED]
        if failed:
            console.print(f"\n[red]{len(failed)} item(s) failed during processing.[/red]")
            if Confirm.ask("Re-queue failed items for retry?", default=False):
                # Reset failed jobs
                for r in failed:
                    for job in self.queue.jobs:
                        if job.path == r.source_path:
                            job.result = None
                            break
                console.print("[green]Failed items re-queued.[/green]")
                time.sleep(1.2)

        Prompt.ask("\nPress Enter to return to main menu")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        help="Launch interactive terminal UI",
    ),
) -> None:
    """Launch Batch Audio Leveler interactive application."""
    if ctx.invoked_subcommand is None:
        from batch_audio_leveler.tui.app import BatchAudioLevelerApp
        tui_app = BatchAudioLevelerApp()
        tui_app.run()


@app.command("process")
def process_cli(
    files: List[Path] = typer.Argument(None, help="MP4 files to normalize"),
    folder: Optional[Path] = typer.Option(None, "--folder", "-f", help="Folder containing MP4 files"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Scan folder recursively"),
    output_dir: Path = typer.Option(
        Path.cwd() / "normalized_output",
        "--output-dir",
        "-o",
        help="Destination directory",
    ),
    mode: str = typer.Option("median", "--mode", "-m", help="Target mode: 'median' or 'fixed'"),
    target_lufs: float = typer.Option(-16.0, "--target", "-t", help="Target LUFS for fixed mode"),
    peak_ceiling: float = typer.Option(-2.0, "--peak", "-p", help="True peak ceiling dBTP"),
    bitrate: str = typer.Option("192k", "--bitrate", "-b", help="AAC audio bitrate"),
    allow_dynamic: bool = typer.Option(False, "--allow-dynamic", help="Allow dynamic loudnorm when peak-limited"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing output files"),
) -> None:
    """Non-interactive batch processing CLI command."""
    config = AppConfig(
        mode=NormalizationMode.BATCH_MEDIAN if mode.lower() == "median" else NormalizationMode.FIXED,
        fixed_target_lufs=target_lufs,
        true_peak_ceiling_dbtp=peak_ceiling,
        audio_bitrate=bitrate,
        allow_dynamic=allow_dynamic,
        output_dir=output_dir,
        overwrite_existing=overwrite,
    )

    errors = config.validate()
    if errors:
        for err in errors:
            console.print(f"[red]Configuration error: {err}[/red]")
        raise typer.Exit(code=1)

    env = discover_ffmpeg(config.ffmpeg_path, config.ffprobe_path)
    if not env.is_ready:
        console.print(f"[red]FFmpeg error: {env.ffmpeg.error_message or 'FFmpeg not ready'}[/red]")
        raise typer.Exit(code=1)

    config.ffmpeg_path = env.ffmpeg.path
    config.ffprobe_path = env.ffprobe.path

    queue = QueueManager()
    if files:
        for f in files:
            queue.add_file(f)
    if folder:
        queue.add_folder(folder, recursive=recursive)

    jobs = queue.jobs
    if not jobs:
        console.print("[red]No valid MP4 files found to process.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[cyan]Loaded {len(jobs)} file(s). Analyzing loudness...[/cyan]")
    for job in jobs:
        try:
            job.probe_result = probe_file(job.path, env.ffprobe.path)
            job.measurement = measure_file_loudness(
                file_path=job.path,
                ffmpeg_path=env.ffmpeg.path,
                stream_index=job.selected_stream_index,
                target_i=config.fixed_target_lufs,
                target_tp=config.true_peak_ceiling_dbtp,
                target_lra=config.target_lra,
            )
        except Exception as e:
            console.print(f"[red]Error analyzing {job.path.name}: {e}[/red]")

    measurements = [j.measurement for j in jobs if j.measurement]
    computed_target = calculate_batch_target(measurements, config)
    console.print(f"[green]Batch Target: {computed_target:.1f} LUFS (Peak ceiling: {config.true_peak_ceiling_dbtp:.1f} dBTP)[/green]")

    for job in jobs:
        if job.measurement:
            job.plan = plan_file_normalization(job.measurement, computed_target, config)

    render_plan_table(jobs, computed_target)
    ensure_directory(config.output_dir)

    results: List[JobResult] = []
    with CancellationToken() as cancel_token:
        for job in jobs:
            if cancel_token.is_cancelled:
                break
            start_time = time.time()
            final_out = get_unique_output_path(config.output_dir, job.path, overwrite=config.overwrite_existing)
            res = JobResult(
                source_path=job.path,
                output_path=final_out,
                status=JobStatus.PROCESSING,
                before_measurement=job.measurement,
                plan=job.plan,
                started_at=datetime.now(timezone.utc).isoformat(),
            )
            if not job.plan or job.plan.planned_mode == "skip":
                res.status = JobStatus.SKIPPED
                res.processing_seconds = time.time() - start_time
                results.append(res)
                continue

            try:
                temp_out = process_file_normalization(
                    input_path=job.path,
                    final_output_path=final_out,
                    plan=job.plan,
                    measurement=job.measurement,
                    config=config,
                    stream_index=job.selected_stream_index,
                    has_subtitles=(job.probe_result.has_subtitles if job.probe_result else False),
                    cancellation_token=cancel_token,
                )
                after_m, warns = verify_normalized_file(
                    output_path=temp_out,
                    plan=job.plan,
                    config=config,
                    stream_index=job.selected_stream_index,
                    cancellation_token=cancel_token,
                )
                if final_out.exists() and config.overwrite_existing:
                    final_out.unlink()
                temp_out.rename(final_out)
                res.after_measurement = after_m
                res.warnings.extend(warns)
                res.status = JobStatus.VERIFIED
            except Exception as e:
                res.status = JobStatus.FAILED
                res.error_message = str(e)

            res.finished_at = datetime.now(timezone.utc).isoformat()
            res.processing_seconds = time.time() - start_time
            results.append(res)

    render_results_table(results)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = config.output_dir / f"batch_report_{timestamp}.csv"
    json_file = config.output_dir / f"batch_report_{timestamp}.json"
    export_csv_report(results, csv_file)
    export_json_report(results, json_file)

    failed_count = sum(1 for r in results if r.status == JobStatus.FAILED)
    if failed_count > 0:
        raise typer.Exit(code=1)
