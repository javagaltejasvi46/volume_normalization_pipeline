"""Modal screen for extracting metadata to CSV and updating files from CSV."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    Static,
    TabbedContent,
    TabPane,
)

from batch_audio_leveler.utils.paths import clean_path


@dataclass
class MetadataTaskConfig:
    action: str  # "export" or "apply"
    source_dir: Path
    output_csv: Optional[Path] = None
    csv_path: Optional[Path] = None
    output_dir: Optional[Path] = None
    recursive: bool = True


class MetadataModal(ModalScreen[Optional[MetadataTaskConfig]]):
    """Modal dialog allowing users to extract metadata to CSV or apply metadata from CSV."""

    DEFAULT_CSS = """
    MetadataModal {
        align: center middle;
    }

    #metadata-dialog {
        width: 86;
        height: 33;
        max-height: 92%;
        background: #14161f;
        border: thick #38bdf8;
        padding: 1 2;
    }

    #metadata-title {
        text-style: bold;
        color: #38bdf8;
        padding-bottom: 1;
        border-bottom: solid #2d3748;
    }

    #meta-tabs {
        height: 1fr;
    }

    .meta-tab-scroll {
        height: 1fr;
        padding: 0 1;
    }

    .meta-desc {
        margin: 1 0;
        color: #94a3b8;
    }

    .meta-label {
        color: #f8fafc;
        margin-top: 1;
        text-style: bold;
    }

    .meta-input {
        background: #15161e;
        border: solid #3b82f6;
    }

    #chk-export-recursive {
        margin: 1 0;
    }

    .in-tab-actions {
        height: auto;
        align: right middle;
        margin-top: 1;
        margin-bottom: 1;
    }

    .in-tab-actions Button {
        margin-left: 1;
    }

    #dialog-footer {
        height: 3;
        dock: bottom;
        align: right middle;
        margin-top: 1;
        border-top: solid #2d3748;
        padding-top: 0;
    }

    #dialog-footer Button {
        margin-left: 1;
        min-width: 18;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        default_dir: Optional[Path] = None,
        default_output_dir: Optional[Path] = None,
        initial_tab: str = "tab-export",
    ) -> None:
        super().__init__()
        self.default_dir = default_dir or Path.cwd()
        self.default_output_dir = default_output_dir or (
            self.default_dir / "metadata_updated"
        )
        self.default_csv = self.default_dir / "media_metadata.csv"
        self.initial_tab = initial_tab

    def compose(self) -> ComposeResult:
        with Container(id="metadata-dialog"):
            yield Label("Metadata Editor (Extract & Apply Tags)", id="metadata-title")
            with TabbedContent(initial=self.initial_tab, id="meta-tabs"):
                # Tab 1: Extract Metadata to CSV
                with TabPane("Part 1: Extract to CSV", id="tab-export"):
                    with VerticalScroll(classes="meta-tab-scroll"):
                        yield Static(
                            "Scan media files in a directory and export their metadata tags "
                            "(Title, Artist, Album, Genre, Year, Track, Comment) into a clean CSV.",
                            classes="meta-desc",
                        )
                        yield Label("Source Media Folder", classes="meta-label")
                        yield Input(
                            value=str(self.default_dir),
                            placeholder="Directory containing media files",
                            id="inp-export-src",
                            classes="meta-input",
                        )
                        yield Label("Destination CSV File Path", classes="meta-label")
                        yield Input(
                            value=str(self.default_csv),
                            placeholder="Path to output .csv file",
                            id="inp-export-csv",
                            classes="meta-input",
                        )
                        yield Checkbox(
                            "Scan subfolders recursively",
                            value=True,
                            id="chk-export-recursive",
                        )
                        with Horizontal(classes="in-tab-actions"):
                            yield Button(
                                "Cancel (Esc)",
                                variant="default",
                                id="btn-export-cancel",
                            )
                            yield Button(
                                "▶ Extract to CSV",
                                variant="primary",
                                id="btn-export-form-submit",
                            )

                # Tab 2: Apply Metadata from CSV
                with TabPane("Part 2: Apply from CSV", id="tab-import"):
                    with VerticalScroll(classes="meta-tab-scroll"):
                        yield Static(
                            "Read metadata tags from a CSV file and apply them to files in the "
                            "source directory, saving updated files losslessly (-c copy) into an output folder.",
                            classes="meta-desc",
                        )
                        yield Label("Metadata CSV File Path", classes="meta-label")
                        yield Input(
                            value=str(self.default_csv),
                            placeholder="Path to CSV file with metadata tags",
                            id="inp-import-csv",
                            classes="meta-input",
                        )
                        yield Label(
                            "Source Media Folder (Originals)",
                            classes="meta-label",
                        )
                        yield Input(
                            value=str(self.default_dir),
                            placeholder="Folder containing original media files",
                            id="inp-import-src",
                            classes="meta-input",
                        )
                        yield Label(
                            "Destination Folder (for updated files)",
                            classes="meta-label",
                        )
                        yield Input(
                            value=str(self.default_output_dir),
                            placeholder="Output folder where updated files will be saved",
                            id="inp-import-dest",
                            classes="meta-input",
                        )
                        with Horizontal(classes="in-tab-actions"):
                            yield Button(
                                "Cancel (Esc)",
                                variant="default",
                                id="btn-import-cancel",
                            )
                            yield Button(
                                "✔ Apply from CSV",
                                variant="success",
                                id="btn-import-form-submit",
                            )

            # Persistent bottom Action Bar (Docked at bottom, ALWAYS VISIBLE!)
            with Horizontal(id="dialog-footer"):
                yield Button(
                    "▶ Extract to CSV",
                    variant="primary" if self.initial_tab == "tab-export" else "default",
                    id="btn-export-submit",
                )
                yield Button(
                    "✔ Apply from CSV",
                    variant="success" if self.initial_tab == "tab-import" else "default",
                    id="btn-import-submit",
                )
                yield Button(
                    "Cancel (Esc)",
                    variant="default",
                    id="btn-cancel",
                )

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Update footer button emphasis based on the active tab."""
        self.update_button_states(event.pane.id)

    def update_button_states(self, active_tab_id: Optional[str]) -> None:
        try:
            btn_export = self.query_one("#btn-export-submit", Button)
            btn_import = self.query_one("#btn-import-submit", Button)
            if active_tab_id == "tab-export":
                btn_export.variant = "primary"
                btn_import.variant = "default"
            elif active_tab_id == "tab-import":
                btn_export.variant = "default"
                btn_import.variant = "success"
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid in ("btn-cancel", "btn-export-cancel", "btn-import-cancel"):
            self.dismiss(None)
        elif bid == "btn-export-form-submit":
            self.submit_export()
        elif bid == "btn-import-form-submit":
            self.submit_import()
        elif bid == "btn-export-submit":
            tabbed = self.query_one("#meta-tabs", TabbedContent)
            if tabbed.active == "tab-export":
                self.submit_export()
            else:
                tabbed.active = "tab-export"
                self.update_button_states("tab-export")
                self.notify("Switched to Extract mode. Click 'Extract to CSV' to proceed.", severity="info")
        elif bid == "btn-import-submit":
            tabbed = self.query_one("#meta-tabs", TabbedContent)
            if tabbed.active == "tab-import":
                self.submit_import()
            else:
                tabbed.active = "tab-import"
                self.update_button_states("tab-import")
                self.notify("Switched to Apply mode. Click 'Apply from CSV' to proceed.", severity="info")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Allow pressing Enter in an input to trigger the respective operation."""
        iid = event.input.id
        if iid in ("inp-export-src", "inp-export-csv"):
            self.submit_export()
        elif iid in ("inp-import-csv", "inp-import-src", "inp-import-dest"):
            self.submit_import()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def submit_export(self) -> None:
        try:
            src_raw = self.query_one("#inp-export-src", Input).value.strip()
            csv_raw = self.query_one("#inp-export-csv", Input).value.strip()
            recursive = self.query_one(
                "#chk-export-recursive", Checkbox
            ).value

            if not src_raw:
                self.notify(
                    "Please provide a source folder path.", severity="error"
                )
                return
            if not csv_raw:
                self.notify(
                    "Please provide a destination CSV file path.",
                    severity="error",
                )
                return

            src_dir = clean_path(src_raw)
            out_csv = clean_path(csv_raw)

            if not src_dir.is_dir():
                self.notify(
                    f"Source folder does not exist:\n{src_dir}",
                    severity="error",
                )
                return

            task = MetadataTaskConfig(
                action="export",
                source_dir=src_dir,
                output_csv=out_csv,
                recursive=recursive,
            )
            self.dismiss(task)
        except Exception as e:
            self.notify(f"Invalid input: {e}", severity="error")

    def submit_import(self) -> None:
        try:
            csv_raw = self.query_one("#inp-import-csv", Input).value.strip()
            src_raw = self.query_one("#inp-import-src", Input).value.strip()
            dest_raw = self.query_one("#inp-import-dest", Input).value.strip()

            if not csv_raw or not src_raw or not dest_raw:
                self.notify(
                    "Please provide CSV path, source folder, and destination folder.",
                    severity="error",
                )
                return

            csv_path = clean_path(csv_raw)
            src_dir = clean_path(src_raw)
            dest_dir = clean_path(dest_raw)

            if not csv_path.is_file():
                self.notify(
                    f"CSV file not found:\n{csv_path}", severity="error"
                )
                return
            if not src_dir.is_dir():
                self.notify(
                    f"Source folder not found:\n{src_dir}", severity="error"
                )
                return

            task = MetadataTaskConfig(
                action="apply",
                source_dir=src_dir,
                csv_path=csv_path,
                output_dir=dest_dir,
            )
            self.dismiss(task)
        except Exception as e:
            self.notify(f"Invalid input: {e}", severity="error")
