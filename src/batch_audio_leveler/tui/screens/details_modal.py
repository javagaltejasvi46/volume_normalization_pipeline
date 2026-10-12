"""File details inspection modal dialog."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from batch_audio_leveler.models import FileJob


class DetailsModal(ModalScreen[None]):
    """Modal screen displaying comprehensive metrics and diagnosis for a single job."""

    DEFAULT_CSS = """
    DetailsModal {
        align: center middle;
    }

    #details-dialog {
        width: 85%;
        max-width: 95;
        height: 80%;
        max-height: 38;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #details-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
        border-bottom: solid $primary;
    }

    #details-scroll {
        height: 1fr;
        margin: 1 0;
    }

    .section-title {
        text-style: bold;
        color: $primary-lighten-2;
        margin-top: 1;
    }

    .detail-row {
        height: auto;
    }

    #details-actions {
        height: auto;
        align: right middle;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("enter", "dismiss", "Close"),
    ]

    def __init__(self, job: FileJob) -> None:
        super().__init__()
        self.job = job

    def compose(self) -> ComposeResult:
        with Container(id="details-dialog"):
            yield Label(f"File Details: {self.job.path.name}", id="details-title")
            with VerticalScroll(id="details-scroll"):
                yield Label("Media Properties", classes="section-title")
                yield Static(f"Full Path: {self.job.path}")
                dur_str = "--"
                v_streams = "--"
                a_streams = "--"
                if self.job.probe_result:
                    if self.job.probe_result.duration_seconds is not None:
                        mins = int(self.job.probe_result.duration_seconds // 60)
                        secs = int(self.job.probe_result.duration_seconds % 60)
                        dur_str = f"{mins}m {secs}s ({self.job.probe_result.duration_seconds:.2f}s)"
                    v_streams = f"{len(self.job.probe_result.video_streams)} video stream(s)"
                    a_streams = f"{len(self.job.probe_result.audio_streams)} audio stream(s)"
                yield Static(f"Duration: {dur_str} | Streams: {v_streams}, {a_streams}")

                yield Label("Pass 1: Loudness Analysis (EBU R128)", classes="section-title")
                m = self.job.measurement
                if m and m.measurement_valid:
                    yield Static(
                        f"Integrated Loudness: {m.integrated_lufs:.2f} LUFS | True Peak: {m.true_peak_dbtp:+.2f} dBTP\n"
                        f"Loudness Range (LRA): {m.loudness_range_lu:.2f} LU | Threshold: {m.threshold_lufs:.2f} LUFS\n"
                        f"Target Offset: {m.target_offset:.2f} LU | Measured At: {m.measured_at or '--'}"
                    )
                elif m and m.is_silent:
                    yield Static("[yellow]Status: Audio is silent or near-silent (<= -70 LUFS / -inf).[/yellow]")
                else:
                    yield Static("[dim]Status: Not analyzed yet.[/dim]")

                yield Label("Normalization Plan", classes="section-title")
                p = self.job.plan
                if p:
                    reachable_str = "[green]Yes[/green]" if p.expected_target_reachable else "[yellow]No (Constrained)[/yellow]"
                    peak_str = "[yellow]Yes[/yellow]" if p.peak_constraint_applied else "[green]No[/green]"
                    eff_gain_str = f"{p.effective_gain_db:+.2f} dB" if p.effective_gain_db is not None else "--"
                    est_peak_str = f"{p.estimated_output_peak_dbtp:+.2f} dBTP" if p.estimated_output_peak_dbtp is not None else "--"
                    yield Static(
                        f"Target LUFS: {p.batch_target_lufs:.2f} LUFS | Requested Gain: {p.requested_gain_db:+.2f} dB\n"
                        f"Effective Gain: {eff_gain_str} | Planned Mode: {p.planned_mode.upper()}\n"
                        f"Peak Ceiling: {p.true_peak_ceiling_dbtp:.2f} dBTP | Est. Output Peak: {est_peak_str}\n"
                        f"Peak Constraint Applied: {peak_str} | Target Reachable: {reachable_str}"
                    )
                    if p.warnings:
                        yield Static("[yellow]Warnings:[/yellow] " + "; ".join(p.warnings))
                else:
                    yield Static("[dim]Plan has not been generated.[/dim]")

                yield Label("Execution & Verification Result", classes="section-title")
                res = self.job.result
                if res:
                    status_color = "green" if res.status.value in {"verified", "completed"} else "red"
                    yield Static(f"Status: [{status_color}]{res.status.value.upper()}[/{status_color}]")
                    if res.output_path:
                        yield Static(f"Output File: {res.output_path}")
                    if res.after_measurement and res.after_measurement.measurement_valid:
                        after_m = res.after_measurement
                        yield Static(
                            f"Verified Output Loudness: {after_m.integrated_lufs:.2f} LUFS | "
                            f"Verified True Peak: {after_m.true_peak_dbtp:+.2f} dBTP"
                        )
                    if res.processing_seconds is not None:
                        yield Static(f"Processing Time: {res.processing_seconds:.2f} seconds")
                    if res.error_message:
                        yield Static(f"[red]Error:[/red] {res.error_message}")
                    if res.warnings:
                        yield Static("[yellow]Verification notes:[/yellow] " + "; ".join(res.warnings))
                else:
                    yield Static("[dim]Not processed yet.[/dim]")

            with Horizontal(id="details-actions"):
                yield Button("Close (Esc)", variant="primary", id="btn-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()
