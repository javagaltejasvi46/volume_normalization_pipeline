"""Textual App implementation for modern full-screen terminal UI."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    ProgressBar,
    Static,
)

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.ffmpeg.analyzer import measure_file_loudness
from batch_audio_leveler.ffmpeg.discovery import FFmpegEnvironment, discover_ffmpeg
from batch_audio_leveler.ffmpeg.probe import probe_file
from batch_audio_leveler.ffmpeg.processor import process_file_normalization
from batch_audio_leveler.ffmpeg.verifier import verify_normalized_file
from batch_audio_leveler.models import (
    FileJob,
    JobResult,
    JobStatus,
    NormalizationMode,
)
from batch_audio_leveler.metadata import (
    apply_metadata_from_csv,
    extract_directory_metadata,
)
from batch_audio_leveler.normalization.planner import plan_file_normalization
from batch_audio_leveler.normalization.targets import calculate_batch_target
from batch_audio_leveler.queue_manager import QueueManager
from batch_audio_leveler.reporting.csv_report import export_csv_report
from batch_audio_leveler.reporting.json_report import export_json_report
from batch_audio_leveler.tui.command_parser import CommandHistory, parse_command_line
from batch_audio_leveler.tui.screens.confirm_modal import ConfirmModal
from batch_audio_leveler.tui.screens.destination_modal import DestinationModal
from batch_audio_leveler.tui.screens.details_modal import DetailsModal
from batch_audio_leveler.tui.screens.help_modal import HelpModal
from batch_audio_leveler.tui.screens.metadata_modal import (
    MetadataModal,
    MetadataTaskConfig,
)
from batch_audio_leveler.tui.screens.settings_modal import SettingsModal
from batch_audio_leveler.utils.cancellation import CancellationToken
from batch_audio_leveler.utils.paths import (
    clean_path,
    ensure_directory,
    format_path_for_display,
    get_unique_output_path,
)


class BatchAudioLevelerApp(App[None]):
    """Modern full-screen TUI application for batch audio loudness normalization."""

    CSS = """
    Screen {
        background: #121317;
        color: #e2e8f0;
    }

    #app-header {
        height: 3;
        background: #1a1c23;
        border-bottom: solid #2d3748;
        padding: 0 1;
        align: left middle;
    }

    #header-title {
        text-style: bold;
        color: #38bdf8;
    }

    #header-status {
        text-align: right;
        color: #94a3b8;
    }

    #summary-bar {
        height: 3;
        background: #181920;
        border-bottom: solid #2d3748;
        padding: 0 1;
        align: left middle;
    }

    .summary-card {
        margin-right: 2;
        padding: 0 1;
        background: #232634;
        border-left: solid #38bdf8;
    }

    #progress-container {
        height: 1;
        display: none;
        margin: 0 1;
    }

    #progress-container.active {
        display: block;
    }

    #main-content {
        height: 1fr;
    }

    #left-panel {
        width: 65%;
        border-right: solid #2d3748;
        padding: 0 1;
    }

    #right-panel {
        width: 35%;
        padding: 0 1;
    }

    #panel-title-queue, #panel-title-log {
        text-style: bold;
        color: #cbd5e1;
        padding: 1 0 0 0;
    }

    DataTable {
        height: 1fr;
        background: #15161e;
        border: solid #2d3748;
    }

    Log {
        height: 1fr;
        background: #15161e;
        border: solid #2d3748;
    }

    #action-bar {
        height: auto;
        background: #181920;
        border-top: solid #2d3748;
        padding: 0 1;
    }

    #quick-buttons {
        height: 3;
        align: left middle;
        margin: 0 0 0 0;
    }

    #quick-buttons Button {
        margin-right: 1;
        min-width: 12;
        height: 3;
    }

    #command-input-container {
        height: 3;
        align: left middle;
    }

    #cmd-input {
        background: #15161e;
        border: solid #3b82f6;
    }
    """

    BINDINGS = [
        Binding("z", "action_run_all", "Auto Run", show=True),
        Binding("a", "action_analyze", "Analyze", show=True),
        Binding("p", "action_preview", "Preview", show=True),
        Binding("x", "action_process", "Process", show=True),
        Binding("space", "action_details", "Details", show=True),
        Binding("s", "action_settings", "Settings", show=True),
        Binding("m", "action_metadata", "Metadata", show=True),
        Binding("r", "action_retry", "Retry Failed", show=False),
        Binding("c", "action_cancel", "Cancel Task", show=True),
        Binding("slash", "focus_command_input", "Command", show=True),
        Binding("colon", "focus_command_input", "Command", show=False),
        Binding("question_mark", "action_help", "Help", show=True),
        Binding("?", "action_help", "Help", show=False),
        Binding("q", "action_quit_app", "Quit", show=True),
    ]

    current_operation = reactive("Ready")
    target_display = reactive("-- LUFS")
    is_busy = reactive(False)

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        super().__init__()
        self.config = config or AppConfig()
        self.queue = QueueManager()
        self.env = discover_ffmpeg(self.config.ffmpeg_path, self.config.ffprobe_path)
        if self.env.ffmpeg.available:
            self.config.ffmpeg_path = self.env.ffmpeg.path
        if self.env.ffprobe.available:
            self.config.ffprobe_path = self.env.ffprobe.path

        self.cancellation_token = CancellationToken()
        self.history = CommandHistory()
        self.results: List[JobResult] = []

    def compose(self) -> ComposeResult:
        # Header bar
        with Horizontal(id="app-header"):
            yield Label("BATCH AUDIO LEVELER  v0.1.0", id="header-title")
            ffmpeg_str = f"FFmpeg {self.env.ffmpeg.version}" if self.env.ffmpeg.available else "FFmpeg Missing"
            yield Label(f"Tools: {ffmpeg_str} | Operation: {self.current_operation}", id="header-status")

        # Summary Metrics Bar
        with Horizontal(id="summary-bar"):
            yield Static("Queue: 0", id="card-queue", classes="summary-card")
            yield Static("Analyzed: 0", id="card-analyzed", classes="summary-card")
            yield Static("Verified: 0", id="card-verified", classes="summary-card")
            yield Static("Failed: 0", id="card-failed", classes="summary-card")
            yield Static("Target: -- LUFS", id="card-target", classes="summary-card")
            yield Static(f"Peak Ceiling: {self.config.true_peak_ceiling_dbtp:.1f} dBTP", id="card-peak", classes="summary-card")

        # Progress bar
        with Container(id="progress-container"):
            yield ProgressBar(id="main-progress", show_eta=False)

        # Main Split Content
        with Horizontal(id="main-content"):
            with Vertical(id="left-panel"):
                yield Label("Queue & Normalization Plan", id="panel-title-queue")
                yield DataTable(id="queue-table")

            with Vertical(id="right-panel"):
                yield Label("Activity & Diagnostics", id="panel-title-log")
                yield Log(id="activity-log", highlight=True)

        # Action & Command Bar
        with Vertical(id="action-bar"):
            with Horizontal(id="quick-buttons"):
                yield Button("Auto Run (Z)", id="btn-run-all", variant="primary")
                yield Button("Analyze (A)", id="btn-analyze", variant="default")
                yield Button("Preview (P)", id="btn-preview", variant="default")
                yield Button("Process (X)", id="btn-process", variant="success")
                yield Button("Details (Space)", id="btn-details", variant="default")
                yield Button("Settings (S)", id="btn-settings", variant="default")
                yield Button("Metadata (M)", id="btn-metadata", variant="default")
                yield Button("Cancel (C)", id="btn-cancel", variant="error")
                yield Button("Help (?)", id="btn-help", variant="default")
                yield Button("Quit (Q)", id="btn-quit", variant="default")

            with Horizontal(id="command-input-container"):
                yield Input(
                    placeholder="Type command: add <file>, folder <dir>, analyze, preview, process, clear, help...",
                    id="cmd-input",
                )

        yield Footer()

    def on_mount(self) -> None:
        """Initialize widgets after mounting."""
        table = self.query_one("#queue-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(
            "#",
            "Filename",
            "Duration",
            "Source LUFS",
            "Source TP",
            "Gain",
            "Mode",
            "Status",
            "Verified LUFS",
        )

        log = self.query_one("#activity-log", Log)
        log.write_line("[bold cyan]Welcome to Batch Audio Leveler.[/bold cyan]")
        log.write_line(f"FFmpeg: {self.env.ffmpeg.path if self.env.ffmpeg.available else 'Not detected'}")
        log.write_line(f"Output directory: {self.config.output_dir}")
        log.write_line("Tip: Press '?' or type 'help' for shortcuts and command syntax.\n")

        self.update_summary_cards()

    def on_resize(self, event: events.Resize) -> None:
        try:
            right = self.query_one("#right-panel")
            left = self.query_one("#left-panel")
            if event.size.width < 90:
                right.styles.display = "none"
                left.styles.width = "100%"
            else:
                right.styles.display = "block"
                left.styles.width = "65%"
        except Exception:
            pass

    def update_summary_cards(self) -> None:
        """Update top status metric blocks."""
        jobs = self.queue.jobs
        total = len(jobs)
        analyzed = sum(1 for j in jobs if j.measurement and j.measurement.measurement_valid)
        verified = sum(1 for j in jobs if j.result and j.result.status == JobStatus.VERIFIED)
        failed = sum(1 for j in jobs if j.result and j.result.status == JobStatus.FAILED)

        self.query_one("#card-queue", Static).update(f"Queue: {total}")
        self.query_one("#card-analyzed", Static).update(f"Analyzed: {analyzed}")
        self.query_one("#card-verified", Static).update(f"Verified: {verified}")
        self.query_one("#card-failed", Static).update(f"Failed: {failed}")
        self.query_one("#card-target", Static).update(f"Target: {self.target_display}")
        self.query_one("#card-peak", Static).update(f"Peak Ceiling: {self.config.true_peak_ceiling_dbtp:.1f} dBTP")

        # Update header status
        status_text = "BUSY (Running)" if self.is_busy else "READY"
        self.query_one("#header-status", Label).update(
            f"Status: {status_text} | Operation: {self.current_operation}"
        )

    def refresh_table(self) -> None:
        """Re-render table rows from queue jobs."""
        table = self.query_one("#queue-table", DataTable)
        current_cursor = table.cursor_row
        table.clear()

        for idx, job in enumerate(self.queue.jobs, 1):
            fname = job.path.name
            dur_str = "--"
            if job.probe_result and job.probe_result.duration_seconds is not None:
                mins = int(job.probe_result.duration_seconds // 60)
                secs = int(job.probe_result.duration_seconds % 60)
                dur_str = f"{mins}m {secs}s"

            m = job.measurement
            src_lufs = f"{m.integrated_lufs:.1f}" if (m and m.integrated_lufs is not None) else "--"
            src_tp = f"{m.true_peak_dbtp:+.1f}" if (m and m.true_peak_dbtp is not None) else "--"

            p = job.plan
            gain_str = f"{p.effective_gain_db:+.1f} dB" if (p and p.effective_gain_db is not None) else "--"
            mode_str = p.planned_mode.capitalize() if p else "--"

            status_str = "Queued"
            ver_lufs = "--"
            if job.result:
                status_str = job.result.status.value.upper()
                if job.result.after_measurement and job.result.after_measurement.integrated_lufs is not None:
                    ver_lufs = f"{job.result.after_measurement.integrated_lufs:.1f}"
            elif job.measurement:
                status_str = "Analyzed"

            table.add_row(
                str(idx),
                fname,
                dur_str,
                src_lufs,
                src_tp,
                gain_str,
                mode_str,
                status_str,
                ver_lufs,
            )

        if current_cursor is not None and current_cursor < len(self.queue.jobs):
            table.move_cursor(row=current_cursor)

        self.update_summary_cards()

    def log_message(self, msg: str, severity: str = "info") -> None:
        """Log a formatted message to the activity panel."""
        log = self.query_one("#activity-log", Log)
        prefix = {
            "info": "[cyan]INFO[/cyan]",
            "success": "[green]SUCCESS[/green]",
            "warning": "[yellow]WARN[/yellow]",
            "error": "[red]ERROR[/red]",
        }.get(severity, "[cyan]INFO[/cyan]")
        log.write_line(f"{prefix}: {msg}")

    # -------------------------------------------------------------------------
    # Command Bar Handling
    # -------------------------------------------------------------------------
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Process entered command line."""
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return

        self.history.add(text)
        cmd = parse_command_line(text)
        if not cmd:
            return

        action = cmd.action
        if action == "add":
            if not cmd.args:
                self.log_message("Usage: add <path_to_mp4>", severity="warning")
            else:
                self.add_file_path(cmd.args[0])
        elif action == "folder":
            if not cmd.args:
                self.log_message("Usage: folder <path_to_folder>", severity="warning")
            else:
                self.add_folder_path(cmd.args[0])
        elif action in {"runall", "run_all", "autorun", "all", "z"}:
            self.action_run_all()
        elif action in {"analyze", "a"}:
            self.action_analyze()
        elif action in {"preview", "p"}:
            self.action_preview()
        elif action in {"process", "x"}:
            self.action_process()
        elif action in {"details", "d", "view"}:
            self.action_details()
        elif action in {"settings", "s", "config"}:
            self.action_settings()
        elif action in {"meta", "metadata", "m"}:
            self.action_metadata()
        elif action in {"meta-export", "export-meta", "export-metadata"}:
            if not cmd.args:
                self.log_message("Usage: meta-export <source_dir> [output_csv_path]", severity="warning")
            else:
                src = clean_path(cmd.args[0])
                csv_p = clean_path(cmd.args[1]) if len(cmd.args) > 1 else (src / "media_metadata.csv")
                task = MetadataTaskConfig(action="export", source_dir=src, output_csv=csv_p, recursive=True)
                self.run_metadata_export_worker(task)
        elif action in {"meta-import", "meta-apply", "apply-meta", "import-meta", "apply-metadata"}:
            if len(cmd.args) < 3:
                self.log_message("Usage: meta-import <csv_path> <source_dir> <output_dir>", severity="warning")
            else:
                csv_p = clean_path(cmd.args[0])
                src = clean_path(cmd.args[1])
                out = clean_path(cmd.args[2])
                task = MetadataTaskConfig(action="apply", source_dir=src, csv_path=csv_p, output_dir=out)
                self.run_metadata_apply_worker(task)
        elif action in {"report", "reports"}:
            self.export_reports()
        elif action in {"retry", "r"}:
            self.action_retry()
        elif action in {"cancel", "c"}:
            self.action_cancel()
        elif action in {"clear", "cls"}:
            self.queue.clear()
            self.refresh_table()
            self.log_message("Queue cleared.", severity="info")
        elif action in {"help", "?"}:
            self.action_help()
        elif action in {"quit", "q", "exit"}:
            self.action_quit_app()
        else:
            self.log_message(f"Unknown command: '{action}'. Type 'help' for commands.", severity="warning")

    def focus_command_input(self) -> None:
        self.query_one("#cmd-input", Input).focus()

    # -------------------------------------------------------------------------
    # File & Folder Addition
    # -------------------------------------------------------------------------
    def add_file_path(self, raw_path: str) -> None:
        path = clean_path(raw_path)
        if not path.is_file():
            self.log_message(f"File not found: '{path}'", severity="error")
            return

        job = self.queue.add_file(path)
        if not job:
            self.log_message(f"Unsupported file format (must be MP4): '{path.name}'", severity="warning")
            return

        if self.env.ffprobe.available and not job.probe_result:
            try:
                job.probe_result = probe_file(job.path, self.env.ffprobe.path)
            except Exception as e:
                self.log_message(f"Probe error on '{job.path.name}': {e}", severity="warning")

        self.refresh_table()
        self.log_message(f"Added '{job.path.name}' to queue.", severity="success")

    def add_folder_path(self, raw_folder: str, recursive: bool = False) -> None:
        folder = clean_path(raw_folder)
        if not folder.is_dir():
            self.log_message(f"Folder not found: '{folder}'", severity="error")
            return

        added = self.queue.add_folder(folder, recursive=recursive)
        if self.env.ffprobe.available:
            for job in self.queue.jobs:
                if not job.probe_result:
                    try:
                        job.probe_result = probe_file(job.path, self.env.ffprobe.path)
                    except Exception:
                        pass

        self.refresh_table()
        self.log_message(f"Added {added} MP4 file(s) from '{folder.name}'.", severity="success")

    # -------------------------------------------------------------------------
    # Asynchronous Workers (Loudness Analysis & Processing)
    # -------------------------------------------------------------------------
    @work(exclusive=True, thread=True)
    def worker_run_all(self) -> None:
        """Automated sequential workflow: Pass 1 Analysis -> Planning -> Pass 2 Normalization & Verification."""
        self.is_busy = True
        self.current_operation = "Auto Run: Analyzing"
        self.cancellation_token = CancellationToken()

        jobs = self.queue.jobs
        total = len(jobs)
        self.call_from_thread(self._start_progress, total)

        # Stage 1: Analyze
        for i, job in enumerate(jobs, 1):
            if self.cancellation_token.is_cancelled:
                self.call_from_thread(self.log_message, "Auto run cancelled during analysis.", "warning")
                self.call_from_thread(self._stop_progress)
                self.is_busy = False
                self.current_operation = "Ready"
                return

            self.call_from_thread(self.log_message, f"Analyzing [{i}/{total}]: {job.path.name}...")
            try:
                m = measure_file_loudness(
                    file_path=job.path,
                    ffmpeg_path=self.config.ffmpeg_path,
                    stream_index=job.selected_stream_index,
                    target_i=self.config.fixed_target_lufs,
                    target_tp=self.config.true_peak_ceiling_dbtp,
                    target_lra=self.config.target_lra,
                    timeout_seconds=self.config.timeout_seconds,
                    cancellation_token=self.cancellation_token,
                )
                job.measurement = m
                if m.is_silent:
                    self.call_from_thread(self.log_message, f"'{job.path.name}' is silent or near-silent.", "warning")
            except Exception as e:
                self.call_from_thread(self.log_message, f"Failed measuring '{job.path.name}': {e}", "error")

            self.call_from_thread(self._step_progress, i)
            self.call_from_thread(self.refresh_table)

        # Stage 2: Target & Planning
        try:
            measurements = [j.measurement for j in jobs if j.measurement]
            target_lufs = calculate_batch_target(measurements, self.config)
            self.target_display = f"{target_lufs:.1f} LUFS"
            for j in jobs:
                if j.measurement:
                    j.plan = plan_file_normalization(j.measurement, target_lufs, self.config)
            self.call_from_thread(self.refresh_table)
            self.call_from_thread(
                self.log_message,
                f"Batch target: {target_lufs:.1f} LUFS. Starting normalization...",
                "success",
            )
        except Exception as e:
            self.call_from_thread(self.log_message, f"Target calculation failed: {e}", "error")
            self.call_from_thread(self._stop_progress)
            self.is_busy = False
            self.current_operation = "Ready"
            return

        # Stage 3: Normalize & Verify
        self.current_operation = "Auto Run: Normalizing"
        ensure_directory(self.config.output_dir)

        for i, job in enumerate(jobs, 1):
            if self.cancellation_token.is_cancelled:
                self.call_from_thread(self.log_message, "Auto run cancelled during normalization.", "warning")
                break

            start_time = time.time()
            now_iso = datetime.now(timezone.utc).isoformat()
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
                started_at=now_iso,
            )
            job.result = res
            self.call_from_thread(self.refresh_table)

            if not job.plan or job.plan.planned_mode == "skip":
                res.status = JobStatus.SKIPPED
                res.warnings.append("Skipped due to silent or unmeasurable audio.")
                res.finished_at = datetime.now(timezone.utc).isoformat()
                res.processing_seconds = time.time() - start_time
                self.results.append(res)
                self.call_from_thread(self._step_progress, i)
                self.call_from_thread(self.refresh_table)
                continue

            self.call_from_thread(self.log_message, f"Normalizing [{i}/{total}]: {job.path.name}...")
            try:
                temp_out = process_file_normalization(
                    input_path=job.path,
                    final_output_path=final_out,
                    plan=job.plan,
                    measurement=job.measurement,
                    config=self.config,
                    stream_index=job.selected_stream_index,
                    has_subtitles=(job.probe_result.has_subtitles if job.probe_result else False),
                    cancellation_token=self.cancellation_token,
                )

                self.call_from_thread(self.log_message, f"Verifying output: {final_out.name}...")
                after_m, warns = verify_normalized_file(
                    output_path=temp_out,
                    plan=job.plan,
                    config=self.config,
                    stream_index=job.selected_stream_index,
                    cancellation_token=self.cancellation_token,
                )

                if final_out.exists() and self.config.overwrite_existing:
                    final_out.unlink()
                temp_out.rename(final_out)

                res.after_measurement = after_m
                res.warnings.extend(warns)
                res.status = JobStatus.VERIFIED
                res.finished_at = datetime.now(timezone.utc).isoformat()
                res.processing_seconds = time.time() - start_time
                self.results.append(res)

                self.call_from_thread(
                    self.log_message,
                    f"Verified '{job.path.name}' -> {after_m.integrated_lufs:.1f} LUFS.",
                    "success",
                )
                if warns:
                    for w in warns:
                        self.call_from_thread(self.log_message, f"  Notice: {w}", "warning")
            except Exception as e:
                res.status = JobStatus.FAILED
                res.error_message = str(e)
                res.finished_at = datetime.now(timezone.utc).isoformat()
                res.processing_seconds = time.time() - start_time
                self.results.append(res)
                self.call_from_thread(self.log_message, f"Failed normalizing '{job.path.name}': {e}", "error")

            self.call_from_thread(self._step_progress, i)
            self.call_from_thread(self.refresh_table)

        self.call_from_thread(self._stop_progress)
        self.is_busy = False
        self.current_operation = "Ready"
        self.call_from_thread(self.export_reports)

    @work(exclusive=True, thread=True)
    def worker_analyze_batch(self) -> None:
        """Run Pass 1 loudness measurement in background thread."""
        self.is_busy = True
        self.current_operation = "Analyzing Batch"
        self.cancellation_token = CancellationToken()

        jobs = self.queue.jobs
        total = len(jobs)
        self.call_from_thread(self._start_progress, total)

        for i, job in enumerate(jobs, 1):
            if self.cancellation_token.is_cancelled:
                self.call_from_thread(self.log_message, "Analysis cancelled by user.", "warning")
                break

            self.call_from_thread(self.log_message, f"Analyzing [{i}/{total}]: {job.path.name}...")
            try:
                m = measure_file_loudness(
                    file_path=job.path,
                    ffmpeg_path=self.config.ffmpeg_path,
                    stream_index=job.selected_stream_index,
                    target_i=self.config.fixed_target_lufs,
                    target_tp=self.config.true_peak_ceiling_dbtp,
                    target_lra=self.config.target_lra,
                    timeout_seconds=self.config.timeout_seconds,
                    cancellation_token=self.cancellation_token,
                )
                job.measurement = m
                if m.is_silent:
                    self.call_from_thread(self.log_message, f"'{job.path.name}' is silent or near-silent.", "warning")
            except Exception as e:
                self.call_from_thread(self.log_message, f"Failed measuring '{job.path.name}': {e}", "error")

            self.call_from_thread(self._step_progress, i)
            self.call_from_thread(self.refresh_table)

        self.call_from_thread(self._stop_progress)
        self.is_busy = False
        self.current_operation = "Ready"

        # Calculate proposed target
        try:
            measurements = [j.measurement for j in jobs if j.measurement]
            target_lufs = calculate_batch_target(measurements, self.config)
            self.target_display = f"{target_lufs:.1f} LUFS"
            for j in jobs:
                if j.measurement:
                    j.plan = plan_file_normalization(j.measurement, target_lufs, self.config)
            self.call_from_thread(self.refresh_table)
            self.call_from_thread(
                self.log_message,
                f"Analysis complete! Batch target calculated: {target_lufs:.1f} LUFS.",
                "success",
            )
        except Exception as e:
            self.call_from_thread(self.log_message, f"Could not compute batch target: {e}", "warning")

    @work(exclusive=True, thread=True)
    def worker_process_batch(self) -> None:
        """Run Pass 2 normalization and Pass 3 verification in background thread."""
        self.is_busy = True
        self.current_operation = "Normalizing Batch"
        self.cancellation_token = CancellationToken()

        jobs = self.queue.jobs
        total = len(jobs)
        self.call_from_thread(self._start_progress, total)
        ensure_directory(self.config.output_dir)

        for i, job in enumerate(jobs, 1):
            if self.cancellation_token.is_cancelled:
                self.call_from_thread(self.log_message, "Batch processing cancelled by user.", "warning")
                break

            start_time = time.time()
            now_iso = datetime.now(timezone.utc).isoformat()
            final_out = get_unique_output_path(self.config.output_dir, job.path, overwrite=self.config.overwrite_existing)

            res = JobResult(
                source_path=job.path,
                output_path=final_out,
                status=JobStatus.PROCESSING,
                before_measurement=job.measurement,
                plan=job.plan,
                started_at=now_iso,
            )
            job.result = res
            self.call_from_thread(self.refresh_table)

            if not job.plan or job.plan.planned_mode == "skip":
                res.status = JobStatus.SKIPPED
                res.warnings.append("Skipped due to silent or unmeasurable audio.")
                res.finished_at = datetime.now(timezone.utc).isoformat()
                res.processing_seconds = time.time() - start_time
                self.results.append(res)
                self.call_from_thread(self._step_progress, i)
                self.call_from_thread(self.refresh_table)
                continue

            self.call_from_thread(self.log_message, f"Normalizing [{i}/{total}]: {job.path.name}...")

            try:
                # Pass 2: Normalize
                temp_out = process_file_normalization(
                    input_path=job.path,
                    final_output_path=final_out,
                    plan=job.plan,
                    measurement=job.measurement,
                    config=self.config,
                    stream_index=job.selected_stream_index,
                    has_subtitles=(job.probe_result.has_subtitles if job.probe_result else False),
                    cancellation_token=self.cancellation_token,
                )

                self.call_from_thread(self.log_message, f"Verifying output: {final_out.name}...")
                # Pass 3: Verification
                after_m, warns = verify_normalized_file(
                    output_path=temp_out,
                    plan=job.plan,
                    config=self.config,
                    stream_index=job.selected_stream_index,
                    cancellation_token=self.cancellation_token,
                )

                if final_out.exists() and self.config.overwrite_existing:
                    final_out.unlink()
                temp_out.rename(final_out)

                res.after_measurement = after_m
                res.warnings.extend(warns)
                res.status = JobStatus.VERIFIED
                res.finished_at = datetime.now(timezone.utc).isoformat()
                res.processing_seconds = time.time() - start_time
                self.results.append(res)

                self.call_from_thread(self.log_message, f"Verified '{job.path.name}' -> {after_m.integrated_lufs:.1f} LUFS.", "success")
                if warns:
                    for w in warns:
                        self.call_from_thread(self.log_message, f"  Notice: {w}", "warning")

            except Exception as e:
                res.status = JobStatus.FAILED
                res.error_message = str(e)
                res.finished_at = datetime.now(timezone.utc).isoformat()
                res.processing_seconds = time.time() - start_time
                self.results.append(res)
                self.call_from_thread(self.log_message, f"Failed normalizing '{job.path.name}': {e}", "error")

            self.call_from_thread(self._step_progress, i)
            self.call_from_thread(self.refresh_table)

        self.call_from_thread(self._stop_progress)
        self.is_busy = False
        self.current_operation = "Ready"

        # Auto-export reports
        self.call_from_thread(self.export_reports)

    def _start_progress(self, total: int) -> None:
        p_container = self.query_one("#progress-container", Container)
        p_container.add_class("active")
        progress = self.query_one("#main-progress", ProgressBar)
        progress.update(total=total, progress=0)

    def _step_progress(self, current: int) -> None:
        progress = self.query_one("#main-progress", ProgressBar)
        progress.update(progress=current)

    def _stop_progress(self) -> None:
        p_container = self.query_one("#progress-container", Container)
        p_container.remove_class("active")

    # -------------------------------------------------------------------------
    # Action Handlers & Shortcuts
    # -------------------------------------------------------------------------
    def action_analyze(self) -> None:
        if self.is_busy:
            self.notify("An operation is already in progress.", severity="warning")
            return
        if not self.queue.jobs:
            self.notify("Queue is empty. Add files first.", severity="warning")
            return
        self.worker_analyze_batch()

    def action_preview(self) -> None:
        jobs = self.queue.jobs
        if not jobs:
            self.notify("Queue is empty.", severity="warning")
            return

        unmeasured = [j for j in jobs if not j.measurement]
        if unmeasured:
            self.log_message(f"{len(unmeasured)} file(s) not analyzed yet. Run Analyze [A] first.", severity="warning")
            return

        try:
            measurements = [j.measurement for j in jobs if j.measurement]
            target_lufs = calculate_batch_target(measurements, self.config)
            self.target_display = f"{target_lufs:.1f} LUFS"
            for j in jobs:
                if j.measurement:
                    j.plan = plan_file_normalization(j.measurement, target_lufs, self.config)
            self.refresh_table()
            self.log_message(f"Normalization preview updated for target {target_lufs:.1f} LUFS.", severity="success")
        except Exception as e:
            self.log_message(f"Error calculating plan: {e}", severity="error")

    def action_run_all(self) -> None:
        """Run Analyze (Pass 1) and Process (Pass 2 + 3) in one automated workflow."""
        if self.is_busy:
            self.notify("An operation is already in progress.", severity="warning")
            return
        if not self.queue.jobs:
            self.notify("Queue is empty. Add files first.", severity="warning")
            return

        def _on_dest_confirmed(chosen_dir: Optional[Path]) -> None:
            if chosen_dir:
                self.config.output_dir = chosen_dir
                self.update_summary_cards()
                self.log_message(f"Destination folder set to: {chosen_dir}", severity="info")
                self.worker_run_all()

        self.push_screen(
            DestinationModal(self.config.output_dir, len(self.queue.jobs), auto_flow=True),
            _on_dest_confirmed,
        )

    def action_process(self) -> None:
        if self.is_busy:
            self.notify("An operation is already in progress.", severity="warning")
            return
        if not self.queue.jobs:
            self.notify("Queue is empty.", severity="warning")
            return

        def _on_dest_confirmed(chosen_dir: Optional[Path]) -> None:
            if chosen_dir:
                self.config.output_dir = chosen_dir
                self.update_summary_cards()
                self.log_message(f"Destination folder set to: {chosen_dir}", severity="info")
                # Ensure plans exist
                unplanned = [j for j in self.queue.jobs if not j.plan]
                if unplanned:
                    self.action_preview()
                self.worker_process_batch()

        self.push_screen(
            DestinationModal(self.config.output_dir, len(self.queue.jobs), auto_flow=False),
            _on_dest_confirmed,
        )

    def action_details(self) -> None:
        table = self.query_one("#queue-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.queue.jobs):
            job = self.queue.jobs[table.cursor_row]
            self.push_screen(DetailsModal(job))
        else:
            self.notify("No file selected in queue.", severity="warning")

    def action_settings(self) -> None:
        def _apply_settings(new_config: Optional[AppConfig]) -> None:
            if new_config:
                self.config = new_config
                self.log_message("Settings updated.", severity="success")
                self.update_summary_cards()
                # Re-preview with new settings if analyzed
                if any(j.measurement for j in self.queue.jobs):
                    self.action_preview()

        self.push_screen(SettingsModal(self.config), _apply_settings)

    def action_retry(self) -> None:
        failed_jobs = [j for j in self.queue.jobs if j.result and j.result.status == JobStatus.FAILED]
        if not failed_jobs:
            self.notify("No failed jobs to retry.", severity="info")
            return

        for j in failed_jobs:
            j.result = None

        self.refresh_table()
        self.log_message(f"Reset {len(failed_jobs)} failed file(s) for retry.", severity="info")
        self.action_process()

    def action_cancel(self) -> None:
        if not self.is_busy:
            self.notify("No active task to cancel.", severity="info")
            return

        self.cancellation_token.cancel()
        self.log_message("Sending cancellation signal to active task...", severity="warning")

    def action_help(self) -> None:
        self.push_screen(HelpModal())

    def action_quit_app(self) -> None:
        if self.is_busy:
            def _confirm_quit(yes: bool) -> None:
                if yes:
                    self.cancellation_token.cancel()
                    self.exit()

            self.push_screen(
                ConfirmModal("An operation is running! Are you sure you want to cancel and quit?"),
                _confirm_quit,
            )
        else:
            self.exit()

    def export_reports(self) -> None:
        if not self.results:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = self.config.output_dir / f"batch_report_{timestamp}.csv"
        json_file = self.config.output_dir / f"batch_report_{timestamp}.json"

        try:
            export_csv_report(self.results, csv_file)
            export_json_report(self.results, json_file)
            self.log_message(f"Reports saved to {csv_file.name} & {json_file.name}", severity="success")
        except Exception as e:
            self.log_message(f"Error exporting reports: {e}", severity="error")

    # Quick button dispatch
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-run-all":
            self.action_run_all()
        elif bid == "btn-analyze":
            self.action_analyze()
        elif bid == "btn-preview":
            self.action_preview()
        elif bid == "btn-process":
            self.action_process()
        elif bid == "btn-details":
            self.action_details()
        elif bid == "btn-settings":
            self.action_settings()
        elif bid == "btn-metadata":
            self.action_metadata()
        elif bid == "btn-cancel":
            self.action_cancel()
        elif bid == "btn-help":
            self.action_help()
        elif bid == "btn-quit":
            self.action_quit_app()

    def action_metadata(self) -> None:
        """Open Metadata Management Hub modal (Part 1: Extract to CSV, Part 2: Apply from CSV)."""
        if self.is_busy:
            self.notify("Another task is currently running. Please wait or cancel.", severity="warning")
            return

        default_dir = Path.cwd()
        if self.queue.jobs:
            default_dir = self.queue.jobs[0].path.parent

        def _handle_metadata_task(task: Optional[MetadataTaskConfig]) -> None:
            if not task:
                return
            if task.action == "export":
                self.run_metadata_export_worker(task)
            elif task.action == "apply":
                self.run_metadata_apply_worker(task)

        self.push_screen(
            MetadataModal(default_dir=default_dir, default_output_dir=self.config.output_dir / "metadata_updated"),
            _handle_metadata_task,
        )

    @work(thread=True)
    def run_metadata_export_worker(self, task: MetadataTaskConfig) -> None:
        if not self.env.ffprobe.available:
            self.call_from_thread(
                self.log_message,
                f"Cannot export metadata: FFprobe is missing.\n{self.env.ffprobe.error_message}",
                "error",
            )
            return

        self.is_busy = True
        self.current_operation = "Exporting Metadata"
        self.call_from_thread(self.update_summary_cards)
        self.call_from_thread(
            self.log_message,
            f"Starting metadata extraction from '{task.source_dir}' -> '{task.output_csv.name}'...",
            "info",
        )

        try:
            count = extract_directory_metadata(
                source_dir=task.source_dir,
                output_csv_path=task.output_csv,
                ffprobe_path=self.env.ffprobe.path,
                recursive=task.recursive,
                log_callback=lambda msg, sev: self.call_from_thread(self.log_message, msg, sev),
            )
            self.call_from_thread(
                self.log_message,
                f"Successfully exported metadata for {count} file(s) to '{task.output_csv}'.",
                "success",
            )
            self.call_from_thread(
                self.notify,
                f"Exported metadata for {count} file(s) to {task.output_csv.name}",
                severity="information",
                timeout=5,
            )
        except Exception as e:
            self.call_from_thread(self.log_message, f"Metadata extraction failed: {e}", "error")
            self.call_from_thread(self.notify, f"Metadata extraction failed: {e}", severity="error", timeout=6)
        finally:
            self.is_busy = False
            self.current_operation = "Ready"
            self.call_from_thread(self.update_summary_cards)

    @work(thread=True)
    def run_metadata_apply_worker(self, task: MetadataTaskConfig) -> None:
        if not self.env.ffmpeg.available:
            self.call_from_thread(
                self.log_message,
                f"Cannot apply metadata: FFmpeg is missing.\n{self.env.ffmpeg.error_message}",
                "error",
            )
            return

        self.is_busy = True
        self.current_operation = "Applying Metadata"
        self.call_from_thread(self.update_summary_cards)
        self.call_from_thread(
            self.log_message,
            f"Starting metadata application from '{task.csv_path.name}' to '{task.source_dir}' -> '{task.output_dir}'...",
            "info",
        )

        try:
            result = apply_metadata_from_csv(
                csv_path=task.csv_path,
                source_dir=task.source_dir,
                output_dir=task.output_dir,
                ffmpeg_path=self.env.ffmpeg.path,
                log_callback=lambda msg, sev: self.call_from_thread(self.log_message, msg, sev),
            )
            self.call_from_thread(
                self.log_message,
                f"Metadata update finished! Updated: {result.updated_count}, Skipped: {result.skipped_count}, Failed: {result.failed_count}",
                "success" if result.failed_count == 0 else "warning",
            )
            self.call_from_thread(
                self.notify,
                f"Updated {result.updated_count}/{result.total_in_csv} file(s) in {task.output_dir.name}",
                severity="information" if result.failed_count == 0 else "warning",
                timeout=5,
            )
        except Exception as e:
            self.call_from_thread(self.log_message, f"Applying metadata failed: {e}", "error")
            self.call_from_thread(self.notify, f"Applying metadata failed: {e}", severity="error", timeout=6)
        finally:
            self.is_busy = False
            self.current_operation = "Ready"
            self.call_from_thread(self.update_summary_cards)
