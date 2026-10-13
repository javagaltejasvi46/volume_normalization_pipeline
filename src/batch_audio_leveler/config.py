"""Configuration and validation for batch audio leveler."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from batch_audio_leveler.models import NormalizationMode


@dataclass
class AppConfig:
    mode: NormalizationMode = NormalizationMode.BATCH_MEDIAN
    fixed_target_lufs: float = -16.0
    true_peak_ceiling_dbtp: float = -2.0
    target_lra: float = 11.0
    max_gain_up_db: float = 12.0
    max_gain_down_db: float = -15.0
    allow_dynamic: bool = False
    audio_bitrate: str = "192k"
    audio_codec: str = "aac"
    output_dir: Path = field(default_factory=lambda: Path.cwd() / "normalized_output")
    include_subfolders: bool = False
    overwrite_existing: bool = False
    loudness_tolerance_lu: float = 1.5
    peak_tolerance_dbtp: float = 0.5
    ffmpeg_path: Optional[Path] = None
    ffprobe_path: Optional[Path] = None
    timeout_seconds: int = 1800

    def __setattr__(self, name: str, value: Any) -> None:
        # LUFS and dBTP are negative decibel scales relative to digital full scale (0 dBFS).
        # Users frequently enter positive numbers (e.g. 15.0 instead of -15.0, or 2.0 instead of -2.0).
        # Automatically negate positive values so downstream FFmpeg loudnorm commands do not fail.
        if name == "fixed_target_lufs" and isinstance(value, (int, float)) and value > 0:
            value = -float(value)
        elif name == "true_peak_ceiling_dbtp" and isinstance(value, (int, float)) and value > 0:
            value = -float(value)
        super().__setattr__(name, value)

    def validate(self) -> list[str]:
        """Validate configuration values and return a list of error strings if any."""
        errors: list[str] = []

        # Validate numeric ranges
        if not math.isfinite(self.fixed_target_lufs) or not (-70.0 <= self.fixed_target_lufs <= -5.0):
            errors.append(f"Fixed target LUFS ({self.fixed_target_lufs}) must be between -70.0 and -5.0.")

        if not math.isfinite(self.true_peak_ceiling_dbtp) or not (-20.0 <= self.true_peak_ceiling_dbtp <= 0.0):
            errors.append(
                f"True peak ceiling dBTP ({self.true_peak_ceiling_dbtp}) must be between -20.0 and 0.0 dBTP."
            )

        if not math.isfinite(self.target_lra) or not (1.0 <= self.target_lra <= 50.0):
            errors.append(f"Target LRA ({self.target_lra}) must be between 1.0 and 50.0 LU.")

        if not math.isfinite(self.max_gain_up_db) or self.max_gain_up_db < 0.0:
            errors.append(f"Max gain-up limit ({self.max_gain_up_db}) must be >= 0.0 dB.")

        if not math.isfinite(self.max_gain_down_db) or self.max_gain_down_db > 0.0:
            errors.append(f"Max gain-down limit ({self.max_gain_down_db}) must be <= 0.0 dB.")

        if self.timeout_seconds <= 0:
            errors.append("Timeout must be greater than 0 seconds.")

        if self.ffmpeg_path and not self.ffmpeg_path.is_file():
            errors.append(f"Configured ffmpeg path does not exist: {self.ffmpeg_path}")

        if self.ffprobe_path and not self.ffprobe_path.is_file():
            errors.append(f"Configured ffprobe path does not exist: {self.ffprobe_path}")

        return errors
