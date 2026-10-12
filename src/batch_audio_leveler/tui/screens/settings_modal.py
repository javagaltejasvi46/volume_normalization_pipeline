"""Settings modal dialog for adjusting normalization parameters."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, RadioButton, RadioSet

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.models import NormalizationMode
from batch_audio_leveler.utils.paths import clean_path


class SettingsModal(ModalScreen[Optional[AppConfig]]):
    """Modal screen for configuring loudness normalization parameters."""

    DEFAULT_CSS = """
    SettingsModal {
        align: center middle;
    }

    #settings-dialog {
        width: 80%;
        max-width: 80;
        height: 85%;
        max-height: 36;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #settings-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
        border-bottom: solid $primary;
    }

    #settings-scroll {
        height: 1fr;
        margin: 1 0;
    }

    .setting-label {
        margin-top: 1;
        text-style: bold;
    }

    #settings-actions {
        height: auto;
        align: right middle;
    }

    #settings-actions Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, current_config: AppConfig) -> None:
        super().__init__()
        self.config = current_config

    def compose(self) -> ComposeResult:
        with Container(id="settings-dialog"):
            yield Label("Configuration & Settings", id="settings-title")
            with VerticalScroll(id="settings-scroll"):
                yield Label("Normalization Mode", classes="setting-label")
                with RadioSet(id="mode-radios"):
                    yield RadioButton(
                        "Batch Median (Align batch to median LUFS)",
                        value=(self.config.mode == NormalizationMode.BATCH_MEDIAN),
                        id="radio-median",
                    )
                    yield RadioButton(
                        "Fixed Target (Specific LUFS target)",
                        value=(self.config.mode == NormalizationMode.FIXED),
                        id="radio-fixed",
                    )

                yield Label("Fixed Target Integrated LUFS (e.g. -16.0)", classes="setting-label")
                yield Input(
                    value=f"{self.config.fixed_target_lufs:.1f}",
                    placeholder="-16.0",
                    id="inp-target-lufs",
                )

                yield Label("True Peak Ceiling dBTP (e.g. -2.0)", classes="setting-label")
                yield Input(
                    value=f"{self.config.true_peak_ceiling_dbtp:.1f}",
                    placeholder="-2.0",
                    id="inp-peak-ceiling",
                )

                yield Label("Audio Bitrate (e.g. 192k, 256k)", classes="setting-label")
                yield Input(
                    value=self.config.audio_bitrate,
                    placeholder="192k",
                    id="inp-bitrate",
                )

                yield Label("Output Directory", classes="setting-label")
                yield Input(
                    value=str(self.config.output_dir),
                    placeholder="Path to output folder",
                    id="inp-output-dir",
                )

                yield Label("Peak Feasibility Policy", classes="setting-label")
                yield Checkbox(
                    "Allow dynamic compression if linear gain hits peak ceiling",
                    value=self.config.allow_dynamic,
                    id="chk-dynamic",
                )

            with Horizontal(id="settings-actions"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Save Settings", variant="primary", id="btn-save")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-save":
            self.save_and_dismiss()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def save_and_dismiss(self) -> None:
        try:
            target_lufs = float(self.query_one("#inp-target-lufs", Input).value)
            peak_ceiling = float(self.query_one("#inp-peak-ceiling", Input).value)
            bitrate = self.query_one("#inp-bitrate", Input).value.strip() or "192k"
            out_dir_raw = self.query_one("#inp-output-dir", Input).value.strip()
            out_dir = clean_path(out_dir_raw)
            allow_dyn = self.query_one("#chk-dynamic", Checkbox).value

            is_fixed = self.query_one("#radio-fixed", RadioButton).value
            mode = NormalizationMode.FIXED if is_fixed else NormalizationMode.BATCH_MEDIAN

            self.config.mode = mode
            self.config.fixed_target_lufs = target_lufs
            self.config.true_peak_ceiling_dbtp = peak_ceiling
            self.config.audio_bitrate = bitrate
            self.config.output_dir = out_dir
            self.config.allow_dynamic = allow_dyn

            self.dismiss(self.config)
        except Exception as e:
            self.notify(f"Invalid input: {e}", severity="error")
