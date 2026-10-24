"""Help modal dialog explaining keyboard shortcuts and commands."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class HelpModal(ModalScreen[None]):
    """Modal screen explaining shortcuts and command bar syntax."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }

    #help-dialog {
        width: 80%;
        max-width: 85;
        height: 80%;
        max-height: 35;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #help-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
        border-bottom: solid $primary;
    }

    #help-scroll {
        height: 1fr;
        margin: 1 0;
    }

    .help-section {
        margin-top: 1;
        text-style: bold;
        color: $primary-lighten-2;
    }

    #help-actions {
        height: auto;
        align: right middle;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("enter", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="help-dialog"):
            yield Label("Keyboard Shortcuts & Commands", id="help-title")
            with VerticalScroll(id="help-scroll"):
                yield Label("Keyboard Shortcuts", classes="help-section")
                yield Static(
                    "  [bold cyan]Z[/bold cyan]      : Auto Run (Analyze & Process batch sequentially in one step)\n"
                    "  [bold cyan]A[/bold cyan]      : Analyze batch (Pass 1 loudness measurement)\n"
                    "  [bold cyan]P[/bold cyan]      : Preview normalization plan table\n"
                    "  [bold cyan]X[/bold cyan]      : Process batch (Pass 2 normalization + Pass 3 verification)\n"
                    "  [bold cyan]Space[/bold cyan]  : Open details for currently highlighted file\n"
                    "  [bold cyan]S[/bold cyan]      : Open settings modal (mode, target LUFS, peak ceiling, etc.)\n"
                    "  [bold cyan]M[/bold cyan]      : Open Metadata Management Hub (Extract/Apply metadata)\n"
                    "  [bold cyan]R[/bold cyan]      : Retry failed items\n"
                    "  [bold cyan]C[/bold cyan]      : Cancel active operation\n"
                    "  [bold cyan]/[/bold cyan] or [bold cyan]:[/bold cyan] : Focus command input bar\n"
                    "  [bold cyan]?[/bold cyan]      : Open this help dialog\n"
                    "  [bold cyan]Q[/bold cyan]      : Quit application (with confirmation if busy)"
                )

                yield Label("Command Bar Commands", classes="help-section")
                yield Static(
                    "Type commands in the bottom command bar and press Enter:\n"
                    "  [bold green]autorun[/bold green]           : Run Analyze & Process sequentially in one step\n"
                    "  [bold green]add <path>[/bold green]        : Add single MP4 file (supports quotes & spaces)\n"
                    "  [bold green]folder <path>[/bold green]     : Add all MP4 files from folder\n"
                    "  [bold green]analyze[/bold green]           : Run Pass 1 loudness measurement\n"
                    "  [bold green]preview[/bold green]           : Generate and preview normalization plan\n"
                    "  [bold green]process[/bold green]           : Normalize and verify all queued files\n"
                    "  [bold green]metadata[/bold green]          : Open metadata extraction & updating dialog\n"
                    "  [bold green]meta-export[/bold green]       : Extract directory tags to CSV (e.g. meta-export <dir> [csv])\n"
                    "  [bold green]meta-import[/bold green]       : Apply CSV tags to directory (e.g. meta-import <csv> <dir> <out>)\n"
                    "  [bold green]settings[/bold green]          : Open settings dialog\n"
                    "  [bold green]report[/bold green]            : Export CSV & JSON reports\n"
                    "  [bold green]retry[/bold green]             : Re-queue failed items for retry\n"
                    "  [bold green]clear[/bold green]             : Clear the current file queue\n"
                    "  [bold green]help[/bold green]              : Show this help modal\n"
                    "  [bold green]quit[/bold green]              : Exit the application"
                )

            with Horizontal(id="help-actions"):
                yield Button("Close (Esc)", variant="primary", id="btn-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()
