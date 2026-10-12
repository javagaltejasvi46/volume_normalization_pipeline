"""Destination directory confirmation and input modal dialog."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from batch_audio_leveler.utils.paths import clean_path, ensure_directory


class DestinationModal(ModalScreen[Optional[Path]]):
    """Modal asking the user to confirm or edit destination directory before processing."""

    DEFAULT_CSS = """
    DestinationModal {
        align: center middle;
    }

    #dest-dialog {
        width: 75;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #dest-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
        border-bottom: solid $primary;
    }

    #dest-desc {
        margin: 1 0;
        color: #cbd5e1;
    }

    #inp-destination {
        margin: 1 0;
        background: #15161e;
        border: solid #38bdf8;
    }

    #dest-actions {
        height: auto;
        align: right middle;
        margin-top: 1;
    }

    #dest-actions Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
    ]

    def __init__(self, current_dir: Path, queue_count: int, auto_flow: bool = False) -> None:
        super().__init__()
        self.current_dir = current_dir
        self.queue_count = queue_count
        self.auto_flow = auto_flow

    def compose(self) -> ComposeResult:
        with Container(id="dest-dialog"):
            flow_title = "Step 2: Choose Destination Folder" if self.auto_flow else "Choose Destination Folder"
            yield Label(flow_title, id="dest-title")
            yield Static(
                f"Enter or paste the folder path where the [bold cyan]{self.queue_count}[/bold cyan] "
                f"normalized videos and reports will be saved:\n"
                f"[dim](Original files are never overwritten)[/dim]",
                id="dest-desc",
            )
            yield Input(
                value=str(self.current_dir),
                placeholder="Folder path (e.g. D:\\Videos\\Normalized)",
                id="inp-destination",
            )
            with Horizontal(id="dest-actions"):
                yield Button("Cancel (Esc)", variant="default", id="btn-cancel")
                yield Button("Start Processing (Enter)", variant="success", id="btn-confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.action_confirm()
        else:
            self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_confirm(self) -> None:
        inp = self.query_one("#inp-destination", Input).value.strip()
        if not inp:
            self.notify("Please enter a destination path.", severity="warning")
            return
        try:
            target_path = clean_path(inp)
            ensure_directory(target_path)
            self.dismiss(target_path)
        except Exception as e:
            self.notify(f"Invalid directory path: {e}", severity="error")
