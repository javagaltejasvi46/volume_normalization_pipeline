"""Modal screen for interactive audio trimming and multi-segment slicing."""

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

from batch_audio_leveler.trimmer.engine import probe_audio_duration
from batch_audio_leveler.trimmer.models import AudioSegment, TrimJobConfig
from batch_audio_leveler.trimmer.parser import format_timestamp, parse_timestamp
from batch_audio_leveler.utils.paths import clean_path


class TrimModal(ModalScreen[Optional[TrimJobConfig]]):
    """Interactive audio trimming dialog with start/end pointers and multi-clip export."""

    DEFAULT_CSS = """
    TrimModal {
        align: center middle;
    }

    #trim-dialog {
        width: 88;
        height: auto;
        max-height: 92%;
        background: #181920;
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
        margin: 1 0;
        color: #94a3b8;
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

    #pointer-row {
        height: auto;
        margin: 1 0;
    }

    .pointer-box {
        width: 1fr;
        margin-right: 1;
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
        margin-bottom: 1;
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
        ffprobe_path: Optional[Path] = None,
    ) -> None:
        super().__init__()
        self.default_file = default_file
        self.default_output_dir = default_output_dir or (Path.cwd() / "trimmed_audio")
        self.ffprobe_path = ffprobe_path
        self.segments: List[AudioSegment] = []
        self.detected_duration: Optional[float] = None

    def compose(self) -> ComposeResult:
        with Container(id="trim-dialog"):
            yield Label("Audio Trimmer & Segment Slicer", id="trim-title")
            with VerticalScroll():
                yield Static(
                    "Set start and end pointer timestamps to extract single or multiple audio clips.",
                    classes="trim-desc",
                )

                yield Label("Audio File Path", classes="trim-label")
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

                yield Label("Add Clip / Segment Pointers", classes="trim-label")
                with Horizontal(id="pointer-row"):
                    with Vertical(classes="pointer-box"):
                        yield Label("Start Time (e.g. 00:15 or 15s)")
                        yield Input(
                            placeholder="00:00",
                            id="inp-trim-start",
                            classes="trim-input",
                        )
                    with Vertical(classes="pointer-box"):
                        yield Label("End Time (e.g. 01:30 or 90s)")
                        yield Input(
                            placeholder="01:30",
                            id="inp-trim-end",
                            classes="trim-input",
                        )
                    with Vertical(classes="pointer-box"):
                        yield Label("Clip Label (optional)")
                        yield Input(
                            placeholder="intro / chorus",
                            id="inp-trim-label",
                            classes="trim-input",
                        )

                with Horizontal():
                    yield Label("Clip Duration: --", id="lbl-segment-duration")

                with Horizontal(classes="table-actions"):
                    yield Button(
                        "+ Add Segment to Export List",
                        variant="primary",
                        id="btn-add-segment",
                    )
                    yield Button(
                        "Remove Selected",
                        variant="default",
                        id="btn-remove-segment",
                    )
                    yield Button(
                        "Clear All",
                        variant="default",
                        id="btn-clear-segments",
                    )

                yield Label("Export Queue (Clips to slice):", classes="trim-label")
                yield DataTable(id="tbl-segments")

                yield Label("Output Audio Format", classes="trim-label")
                with RadioSet(id="format-radios"):
                    yield RadioButton(
                        "Export as MP3 (.mp3, high-quality 192kbps)",
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
                    placeholder="Folder path for trimmed clips",
                    id="inp-trim-dest",
                    classes="trim-input",
                )

                with Horizontal(classes="trim-actions"):
                    yield Button(
                        "Cancel (Esc)", variant="default", id="btn-trim-cancel"
                    )
                    yield Button(
                        "Export Trimmed Clips",
                        variant="success",
                        id="btn-trim-submit",
                    )

    def on_mount(self) -> None:
        table = self.query_one("#tbl-segments", DataTable)
        table.cursor_type = "row"
        table.add_columns("#", "Start", "End", "Duration", "Label")
        if self.default_file and self.default_file.is_file():
            self.inspect_file(self.default_file)

    def inspect_file(self, file_path: Path) -> None:
        """Inspect file duration if ffprobe is configured."""
        lbl_info = self.query_one("#lbl-file-info", Label)
        if self.ffprobe_path and self.ffprobe_path.is_file():
            dur = probe_audio_duration(file_path, self.ffprobe_path)
            self.detected_duration = dur
            if dur is not None:
                lbl_info.update(f"Detected Duration: {format_timestamp(dur)} ({dur:.1f}s)")
            else:
                lbl_info.update("Detected Duration: Unknown / Unable to probe")
        else:
            lbl_info.update(f"Source file: {file_path.name}")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Update live duration preview as user types timestamps or changes file."""
        if event.input.id == "inp-trim-src":
            p = clean_path(event.value.strip())
            if p.is_file():
                self.inspect_file(p)
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
                lbl.update("Clip Duration: [bold red]End time must be greater than start time[/bold red]")
        except Exception:
            lbl.update("Clip Duration: [yellow]Waiting for valid timestamps...[/yellow]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-trim-cancel":
            self.dismiss(None)
        elif bid == "btn-add-segment":
            self.add_segment_from_form()
        elif bid == "btn-remove-segment":
            self.remove_selected_segment()
        elif bid == "btn-clear-segments":
            self.clear_all_segments()
        elif bid == "btn-trim-submit":
            self.submit_trim_job()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def add_segment_from_form(self) -> bool:
        start_raw = self.query_one("#inp-trim-start", Input).value.strip()
        end_raw = self.query_one("#inp-trim-end", Input).value.strip()
        label_raw = self.query_one("#inp-trim-label", Input).value.strip()

        if not start_raw or not end_raw:
            self.notify("Please provide both start and end pointers.", severity="error")
            return False

        try:
            start_s = parse_timestamp(start_raw)
            end_s = parse_timestamp(end_raw)
        except Exception as e:
            self.notify(f"Invalid timestamp format: {e}", severity="error")
            return False

        if end_s <= start_s:
            self.notify("End time must be greater than start time.", severity="error")
            return False

        if self.detected_duration and end_s > self.detected_duration:
            self.notify(
                f"Warning: End pointer ({format_timestamp(end_s)}) exceeds file duration ({format_timestamp(self.detected_duration)}).",
                severity="warning",
            )

        seg = AudioSegment(start_seconds=start_s, end_seconds=end_s, label=label_raw)
        self.segments.append(seg)
        self.refresh_segments_table()

        # Reset pointer inputs for next clip
        self.query_one("#inp-trim-start", Input).value = ""
        self.query_one("#inp-trim-end", Input).value = ""
        self.query_one("#inp-trim-label", Input).value = ""
        self.query_one("#lbl-segment-duration", Label).update("Clip Duration: --")
        self.notify(f"Added segment: {format_timestamp(start_s)} to {format_timestamp(end_s)}", severity="info")
        return True

    def refresh_segments_table(self) -> None:
        table = self.query_one("#tbl-segments", DataTable)
        table.clear()
        for idx, seg in enumerate(self.segments, 1):
            table.add_row(
                str(idx),
                format_timestamp(seg.start_seconds),
                format_timestamp(seg.end_seconds),
                f"{seg.duration_seconds:.1f}s",
                seg.label or f"clip_{idx}",
            )

    def remove_selected_segment(self) -> None:
        table = self.query_one("#tbl-segments", DataTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.segments):
            removed = self.segments.pop(table.cursor_row)
            self.refresh_segments_table()
            self.notify(f"Removed segment {format_timestamp(removed.start_seconds)} - {format_timestamp(removed.end_seconds)}", severity="info")
        else:
            self.notify("No segment selected in the table to remove.", severity="warning")

    def clear_all_segments(self) -> None:
        self.segments.clear()
        self.refresh_segments_table()
        self.notify("Export list cleared.", severity="info")

    def submit_trim_job(self) -> None:
        src_raw = self.query_one("#inp-trim-src", Input).value.strip()
        dest_raw = self.query_one("#inp-trim-dest", Input).value.strip()

        if not src_raw:
            self.notify("Please enter the audio file path.", severity="error")
            return

        src_path = clean_path(src_raw)
        if not src_path.is_file():
            self.notify(f"Source audio file not found:\n{src_path}", severity="error")
            return

        dest_dir = clean_path(dest_raw) if dest_raw else self.default_output_dir

        # If table is empty but start and end pointers are entered in the form, automatically add it!
        if not self.segments:
            start_raw = self.query_one("#inp-trim-start", Input).value.strip()
            end_raw = self.query_one("#inp-trim-end", Input).value.strip()
            if start_raw and end_raw:
                if not self.add_segment_from_form():
                    return
            else:
                self.notify("Please enter start/end pointers and add at least one segment.", severity="error")
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
