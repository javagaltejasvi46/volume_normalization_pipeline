"""Confirmation modal dialog for destructive or interruptive actions."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmModal(ModalScreen[bool]):
    """Generic confirmation dialog."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }

    #confirm-dialog {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }

    #confirm-message {
        margin: 1 0;
        text-align: center;
    }

    #confirm-actions {
        height: auto;
        align: center middle;
    }

    #confirm-actions Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
    ]

    def __init__(self, message: str, title: str = "Confirm Action") -> None:
        super().__init__()
        self.message = message
        self.title_text = title

    def compose(self) -> ComposeResult:
        with Container(id="confirm-dialog"):
            yield Label(self.title_text, id="confirm-title")
            yield Label(self.message, id="confirm-message")
            with Horizontal(id="confirm-actions"):
                yield Button("Cancel (Esc)", variant="default", id="btn-cancel")
                yield Button("Yes, Confirm (Enter)", variant="error", id="btn-confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)
