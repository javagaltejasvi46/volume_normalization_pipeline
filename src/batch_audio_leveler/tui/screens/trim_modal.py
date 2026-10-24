"""Interactive visual audio trimmer modal with wavegraph, pointer placement, and collision alerts."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
)

from batch_audio_leveler.trimmer.collisions import (
    find_segment_collisions,
    validate_segments_for_export,
)
from batch_audio_leveler.trimmer.engine import probe_audio_duration
from batch_audio_leveler.trimmer.models import AudioSegment, TrimJobConfig
from batch_audio_leveler.trimmer.parser import format_timestamp, parse_timestamp
from batch_audio_leveler.trimmer.waveform import (
    extract_waveform_envelope,
    render_ascii_waveform,
)
from batch_audio_leveler.utils.paths import clean_path


class TrimModal(ModalScreen[Optional[TrimJobConfig]]):
    """Visual audio trimmer modal with wavegraph, interactive pointer placement, and collision alerts."""

    DEFAULT_CSS = """
    TrimModal {
        align: center middle;
    }

    #trim-dialog {
        width: 90;
        height: auto;
        max-height: 94%;
        background: #14161f;
        border: thick #38bdf8;
        padding: 1 2;
    }

    #trim-title {
        text-style: bold;
        color: #38bdf8;
        padding-bottom: 1;
        border-bottom: solid #2d3748;
    }

    .trim-desc {
        color: #94a3b8;
        margin-bottom: 1;
    }

    .trim-label {
        color: #f8fafc;
        margin-top: 1;
        text-style: bold;
    }

    .trim-input {
        background: #15161e;
        border: solid #3b82f6;
    }

    #waveform-container {
        height: auto;
        background: #0d0f17;
        border: solid #1e293b;
        padding: 1;
        margin: 1 0;
    }

    #waveform-canvas {
        width: 100%;
        height: auto;
    }

    #collision-alert {
        height: auto;
        padding: 0 1;
        margin: 1 0;
        text-style: bold;
    }

    .alert-clean {
        color: #4ade80;
        background: #052e16;
        border-left: solid #22c55e;
    }

    .alert-collision {
        color: #fca5a5;
        background: #450a0a;
        border-left: solid #ef4444;
    }

    #pointer-row {
        height: auto;
        margin: 1 0;
    }

    .pointer-box {
        width: 1fr;
        margin-right: 1;
    }

    .stepper-row {
        height: 3;
        margin-top: 1;
    }

    .stepper-row Button {
        min-width: 5;
        height: 3;
        margin-right: 1;
        padding: 0 1;
    }

    #lbl-segment-duration {
        color: #38bdf8;
        text-style: bold;
        margin-top: 1;
    }

    #tbl-segments {
        height: 6;
        background: #15161e;
        border: solid #2d3748;
        margin: 1 0;
    }

    .table-actions {
        height: auto;
        margin: 1 0;
    }

    .table-actions Button {
        margin-right: 1;
    }

    #format-radios {
        height: auto;
        margin: 1 0;
    }

    .trim-actions {
        height: auto;
        align: right middle;
        margin-top: 1;
    }

    .trim-actions Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        default_file: Optional[Path] = None,
        default_output_dir: Optional[Path] = None,
        ffmpeg_path: Optional[Path] = None,
        ffprobe_path: Optional[Path] = None,
    ) -> None:
        super().__init__()
        self.default_file = default_file
        self.default_output_dir = default_output_dir or (Path.cwd() / "trimmed_audio")
        self.ffmpeg_path = ffmpeg_path or Path("ffmpeg.exe")
        self.ffprobe_path = ffprobe_path or Path("ffprobe.exe")
        self.segments: List[AudioSegment] = []
        self.detected_duration: float = 60.0
        self.amplitudes: List[float] = [0.1] * 72
        self.active_segment_idx: Optional[int] = None

    def compose(self) -> ComposeResult:
        with Container(id="trim-dialog"):
            yield Label("Visual Audio Trimmer & Multi-Segment Slicer", id="trim-title")
            with VerticalScroll():
                yield Static(
                    "Inspect audio wavegraph, place start/end pointers visually, and slice multiple clips at once.",
                    classes="trim-desc",
                )

                yield Label("Audio Source File", classes="trim-label")
                yield Input(
                    value=str(self.default_file) if self.default_file else "",
                    placeholder="Path to audio file (.mp3, .wav, .m4a, .flac, .mp4, etc.)",
                    id="inp-trim-src",
                    classes="trim-input",
                )
                yield Label(
                    "Detected Duration: --",
                    id="lbl-file-info",
                    classes="trim-desc",
                )

                # Audio Wavegraph Display
                yield Label("Audio Wavegraph & Visual Pointer Timeline", classes="trim-label")
                with Container(id="waveform-container"):
                    yield Static("Loading audio waveform...", id="waveform-canvas")

                # Collision Alert Banner
                yield Static(
                    "✔ Pointers are collision-free.",
                    id="collision-alert",
                    classes="alert-clean",
                )

                # Pointer Placement Form & Steppers
                yield Label("Set Start & End Pointers", classes="trim-label")
                with Horizontal(id="pointer-row"):
                    with Vertical(classes="pointer-box"):
                        yield Label("Start Time (e.g. 00:15 or 15s)")
                        yield Input(
                            placeholder="00:00",
                            id="inp-trim-start",
                            classes="trim-input",
                        )
                        with Horizontal(classes="stepper-row"):
                            yield Button("-5s", id="btn-start-m5", variant="default")
                            yield Button("-1s", id="btn-start-m1", variant="default")
                            yield Button("+1s", id="btn-start-p1", variant="default")
                            yield Button("+5s", id="btn-start-p5", variant="default")

                    with Vertical(classes="pointer-box"):
                        yield Label("End Time (e.g. 01:30 or 90s)")
                        yield Input(
                            placeholder="01:30",
                            id="inp-trim-end",
                            classes="trim-input",
                        )
                        with Horizontal(classes="stepper-row"):
                            yield Button("-5s", id="btn-end-m5", variant="default")
                            yield Button("-1s", id="btn-end-m1", variant="default")
                            yield Button("+1s", id="btn-end-p1", variant="default")
                            yield Button("+5s", id="btn-end-p5", variant="default")

                    with Vertical(classes="pointer-box"):
                        yield Label("Clip Label (optional)")
                        yield Input(
                            placeholder="intro / chorus",
                            id="inp-trim-label",
                            classes="trim-input",
                        )
                        yield Label("Clip Duration: --", id="lbl-segment-duration")

                with Horizontal(classes="table-actions"):
                    yield Button("+ Add Segment", variant="primary", id="btn-add-segment")
                    yield Button("Update Current", variant="default", id="btn-update-segment")
                    yield Button("Remove Selected", variant="error", id="btn-remove-segment")
                    yield Button("Clear All", variant="default", id="btn-clear-segments")

                # Segments Table
                yield Label("Segment Cue List (All clips to export):", classes="trim-label")
                yield DataTable(id="tbl-segments")

                # Output Format
                yield Label("Output Audio Format", classes="trim-label")
                with RadioSet(id="format-radios"):
                    yield RadioButton(
                        "Export as MP3 (.mp3, high-compatibility 192k)",
                        value=True,
                        id="radio-fmt-mp3",
                    )
                    yield RadioButton(
                        "Keep Original Audio Format (lossless copy)",
                        value=False,
                        id="radio-fmt-orig",
                    )

                yield Label("Output Destination Folder", classes="trim-label")
                yield Input(
                    value=str(self.default_output_dir),
                    placeholder="Folder path for exported clips",
                    id="inp-trim-dest",
                    classes="trim-input",
                )

                with Horizontal(classes="trim-actions"):
                    yield Button("Cancel (Esc)", variant="default", id="btn-trim-cancel")
                    yield Button(
                        "Export All Clips (Enter)",
                        variant="success",
                        id="btn-trim-submit",
                    )

    def on_mount(self) -> None:
        table = self.query_one("#tbl-segments", DataTable)
        table.cursor_type = "row"
        table.add_columns("#", "Start", "End", "Duration", "Label", "Collision Status")
        if self.default_file and self.default_file.is_file():
            self.load_audio_file(self.default_file)

    def load_audio_file(self, file_path: Path) -> None:
        """Probe duration and extract waveform envelope for visual wavegraph."""
        lbl_info = self.query_one("#lbl-file-info", Label)
        dur = probe_audio_duration(file_path, self.ffprobe_path)
        if dur and dur > 0:
            self.detected_duration = dur
            lbl_info.update(f"Detected Duration: [bold green]{format_timestamp(dur)} ({dur:.1f}s)[/bold green]")
        else:
            self.detected_duration = 60.0
            lbl_info.update(f"Source file: {file_path.name} (Duration unprobed)")

        # Extract waveform envelope
        self.amplitudes = extract_waveform_envelope(
            file_path, self.ffmpeg_path, num_bars=72
        )
        self.refresh_visuals()

    def refresh_visuals(self) -> None:
        """Re-render visual wavegraph and collision alert banner."""
        canvas = self.query_one("#waveform-canvas", Static)
        rendered = render_ascii_waveform(
            amplitudes=self.amplitudes,
            segments=self.segments,
            total_duration=self.detected_duration,
            width=72,
            height=3,
            active_segment_index=self.active_segment_idx,
        )
        canvas.update(rendered)

        # Check collisions
        collisions = find_segment_collisions(self.segments)
        banner = self.query_one("#collision-alert", Static)

        if collisions:
            banner.remove_class("alert-clean")
            banner.add_class("alert-collision")
            desc_lines = [c.description() for c in collisions]
            banner.update(
                f"[bold red]⚠ COLLISION DETECTED ({len(collisions)} overlap):[/bold red]\n"
                + "\n".join(f"  • {d}" for d in desc_lines)
                + "\n[yellow]Please adjust start/end pointers to resolve overlap before exporting.[/yellow]"
            )
        else:
            banner.remove_class("alert-collision")
            banner.add_class("alert-clean")
            banner.update(
                f"✔ All {len(self.segments)} segment pointer(s) are collision-free and ready to export."
                if self.segments
                else "✔ Pointers are collision-free."
            )

        self.refresh_segments_table()

    def refresh_segments_table(self) -> None:
        table = self.query_one("#tbl-segments", DataTable)
        table.clear()
        collisions = find_segment_collisions(self.segments)
        colliding_indices = set()
        for c in collisions:
            colliding_indices.add(c.index_a)
            colliding_indices.add(c.index_b)

        for idx, seg in enumerate(self.segments, 1):
            s_idx = idx - 1
            is_coll = s_idx in colliding_indices
            status_str = "[bold red]COLLISION[/bold red]" if is_coll else "[green]OK[/green]"
            table.add_row(
                str(idx),
                format_timestamp(seg.start_seconds),
                format_timestamp(seg.end_seconds),
                f"{seg.duration_seconds:.1f}s",
                seg.label or f"clip_{idx}",
                status_str,
            )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "inp-trim-src":
            p = clean_path(event.value.strip())
            if p.is_file():
                self.load_audio_file(p)
        elif event.input.id in ("inp-trim-start", "inp-trim-end"):
            self.update_live_duration()

    def update_live_duration(self) -> None:
        lbl = self.query_one("#lbl-segment-duration", Label)
        start_raw = self.query_one("#inp-trim-start", Input).value.strip()
        end_raw = self.query_one("#inp-trim-end", Input).value.strip()
        if not start_raw or not end_raw:
            lbl.update("Clip Duration: --")
            return

        try:
            s = parse_timestamp(start_raw)
            e = parse_timestamp(end_raw)
            if e > s:
                dur = e - s
                lbl.update(f"Clip Duration: [bold green]{format_timestamp(dur)} ({dur:.1f}s)[/bold green]")
            else:
                lbl.update("Clip Duration: [bold red]End time must be > start[/bold red]")
        except Exception:
            lbl.update("Clip Duration: [yellow]Waiting for valid timestamps...[/yellow]")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """When user selects a segment in the table, load its pointers into the form for editing."""
        if event.cursor_row is not None and 0 <= event.cursor_row < len(self.segments):
            self.active_segment_idx = event.cursor_row
            seg = self.segments[self.active_segment_idx]
            self.query_one("#inp-trim-start", Input).value = format_timestamp(seg.start_seconds)
            self.query_one("#inp-trim-end", Input).value = format_timestamp(seg.end_seconds)
            self.query_one("#inp-trim-label", Input).value = seg.label
            self.update_live_duration()
            self.refresh_visuals()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-trim-cancel":
            self.dismiss(None)
        elif bid == "btn-add-segment":
            self.add_segment_from_form()
        elif bid == "btn-update-segment":
            self.update_active_segment()
        elif bid == "btn-remove-segment":
            self.remove_selected_segment()
        elif bid == "btn-clear-segments":
            self.clear_all_segments()
        elif bid == "btn-trim-submit":
            self.submit_trim_job()
        # Stepper buttons
        elif bid == "btn-start-m5":
            self.nudge_time("inp-trim-start", -5.0)
        elif bid == "btn-start-m1":
            self.nudge_time("inp-trim-start", -1.0)
        elif bid == "btn-start-p1":
            self.nudge_time("inp-trim-start", +1.0)
        elif bid == "btn-start-p5":
            self.nudge_time("inp-trim-start", +5.0)
        elif bid == "btn-end-m5":
            self.nudge_time("inp-trim-end", -5.0)
        elif bid == "btn-end-m1":
            self.nudge_time("inp-trim-end", -1.0)
        elif bid == "btn-end-p1":
            self.nudge_time("inp-trim-end", +1.0)
        elif bid == "btn-end-p5":
            self.nudge_time("inp-trim-end", +5.0)

    def nudge_time(self, input_id: str, delta: float) -> None:
        inp = self.query_one(f"#{input_id}", Input)
        val_str = inp.value.strip() or "00:00"
        try:
            curr = parse_timestamp(val_str)
            new_val = max(0.0, curr + delta)
            if self.detected_duration:
                new_val = min(self.detected_duration, new_val)
            inp.value = format_timestamp(new_val)
            self.update_live_duration()
        except Exception:
            pass

    def action_cancel(self) -> None:
        self.dismiss(None)

    def add_segment_from_form(self) -> bool:
        start_raw = self.query_one("#inp-trim-start", Input).value.strip()
        end_raw = self.query_one("#inp-trim-end", Input).value.strip()
        label_raw = self.query_one("#inp-trim-label", Input).value.strip()

        if not start_raw or not end_raw:
            self.notify("Please enter both start and end pointer timestamps.", severity="error")
            return False

        try:
            start_s = parse_timestamp(start_raw)
            end_s = parse_timestamp(end_raw)
        except Exception as e:
            self.notify(f"Invalid timestamp format: {e}", severity="error")
            return False

        if end_s <= start_s:
            self.notify("End pointer must be greater than start pointer.", severity="error")
            return False

        seg = AudioSegment(start_seconds=start_s, end_seconds=end_s, label=label_raw)
        self.segments.append(seg)
        self.active_segment_idx = len(self.segments) - 1
        self.refresh_visuals()

        # Check if this new segment caused a collision
        collisions = find_segment_collisions(self.segments)
        if collisions:
            self.notify(
                f"Warning: Segment collision detected with existing clips!",
                severity="warning",
                timeout=5,
            )
        else:
            self.notify(f"Added Segment {len(self.segments)}: {format_timestamp(start_s)} - {format_timestamp(end_s)}", severity="info")

        # Clear form inputs for next clip
        self.query_one("#inp-trim-start", Input).value = ""
        self.query_one("#inp-trim-end", Input).value = ""
        self.query_one("#inp-trim-label", Input).value = ""
        self.query_one("#lbl-segment-duration", Label).update("Clip Duration: --")
        return True

    def update_active_segment(self) -> None:
        table = self.query_one("#tbl-segments", DataTable)
        idx = table.cursor_row if table.cursor_row is not None else self.active_segment_idx
        if idx is None or idx < 0 or idx >= len(self.segments):
            self.notify("No segment selected to update. Click a row in the table first.", severity="warning")
            return

        start_raw = self.query_one("#inp-trim-start", Input).value.strip()
        end_raw = self.query_one("#inp-trim-end", Input).value.strip()
        label_raw = self.query_one("#inp-trim-label", Input).value.strip()

        try:
            start_s = parse_timestamp(start_raw)
            end_s = parse_timestamp(end_raw)
        except Exception as e:
            self.notify(f"Invalid timestamp: {e}", severity="error")
            return

        if end_s <= start_s:
            self.notify("End pointer must be greater than start pointer.", severity="error")
            return

        self.segments[idx] = AudioSegment(start_seconds=start_s, end_seconds=end_s, label=label_raw)
        self.refresh_visuals()
        self.notify(f"Updated Segment {idx + 1} pointers.", severity="info")

    def remove_selected_segment(self) -> None:
        table = self.query_one("#tbl-segments", DataTable)
        idx = table.cursor_row if table.cursor_row is not None else self.active_segment_idx
        if idx is not None and 0 <= idx < len(self.segments):
            removed = self.segments.pop(idx)
            self.active_segment_idx = None
            self.refresh_visuals()
            self.notify(f"Removed segment: {format_timestamp(removed.start_seconds)} - {format_timestamp(removed.end_seconds)}", severity="info")
        else:
            self.notify("Select a segment in the table to remove.", severity="warning")

    def clear_all_segments(self) -> None:
        self.segments.clear()
        self.active_segment_idx = None
        self.refresh_visuals()
        self.notify("All segments cleared.", severity="info")

    def submit_trim_job(self) -> None:
        src_raw = self.query_one("#inp-trim-src", Input).value.strip()
        dest_raw = self.query_one("#inp-trim-dest", Input).value.strip()

        if not src_raw:
            self.notify("Please enter audio source file path.", severity="error")
            return

        src_path = clean_path(src_raw)
        if not src_path.is_file():
            self.notify(f"Source audio file not found:\n{src_path}", severity="error")
            return

        dest_dir = clean_path(dest_raw) if dest_raw else self.default_output_dir

        # If table is empty but form inputs have start/end, automatically add it
        if not self.segments:
            start_raw = self.query_one("#inp-trim-start", Input).value.strip()
            end_raw = self.query_one("#inp-trim-end", Input).value.strip()
            if start_raw and end_raw:
                if not self.add_segment_from_form():
                    return
            else:
                self.notify("Please add at least one segment to export.", severity="error")
                return

        # COLLISION CHECK: Alert user and prevent export if collision exists!
        collisions = find_segment_collisions(self.segments)
        if collisions:
            desc = collisions[0].description()
            self.notify(
                f"Collision detected! Cannot export overlapping clips:\n{desc}\nPlease adjust pointers.",
                severity="error",
                timeout=7,
            )
            return

        # Check general validity
        errors = validate_segments_for_export(self.segments, self.detected_duration)
        if errors:
            self.notify(f"Cannot export: {errors[0]}", severity="error")
            return

        is_mp3 = self.query_one("#radio-fmt-mp3", RadioButton).value
        out_fmt = "mp3" if is_mp3 else "original"

        cfg = TrimJobConfig(
            source_file=src_path,
            segments=list(self.segments),
            output_dir=dest_dir,
            output_format=out_fmt,
        )
        self.dismiss(cfg)
