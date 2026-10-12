"""Execution of Pass 2 audio normalization."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.ffmpeg.command_builder import build_normalization_command
from batch_audio_leveler.models import AudioMeasurement, NormalizationPlan
from batch_audio_leveler.utils.cancellation import CancellationToken
from batch_audio_leveler.utils.paths import get_temp_output_path


class ProcessingError(Exception):
    """Raised when normalization execution fails."""
    pass


def process_file_normalization(
    input_path: Path,
    final_output_path: Path,
    plan: NormalizationPlan,
    measurement: AudioMeasurement,
    config: AppConfig,
    stream_index: int = 0,
    has_subtitles: bool = False,
    cancellation_token: Optional[CancellationToken] = None,
) -> Path:
    """Normalize input_path into a temporary output file and return temp path.

    Cleans up temporary file on failure or cancellation.
    """
    if not config.ffmpeg_path or not config.ffmpeg_path.is_file():
        raise ProcessingError("FFmpeg binary path is not configured or does not exist.")

    temp_path = get_temp_output_path(final_output_path)
    cmd = build_normalization_command(
        ffmpeg_path=config.ffmpeg_path,
        input_path=input_path,
        output_path=temp_path,
        plan=plan,
        measurement=measurement,
        config=config,
        stream_index=stream_index,
        has_subtitles=has_subtitles,
    )

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise ProcessingError(f"Failed to start FFmpeg for '{input_path.name}': {e}") from e

    if cancellation_token:
        cancellation_token.register_process(proc)

    try:
        stdout_text, stderr_text = proc.communicate(timeout=config.timeout_seconds)
    except subprocess.TimeoutExpired as e:
        proc.kill()
        proc.communicate()
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise ProcessingError(f"Normalization timed out after {config.timeout_seconds}s for '{input_path.name}'.") from e
    finally:
        if cancellation_token:
            cancellation_token.unregister_process()

    if cancellation_token and cancellation_token.is_cancelled:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise ProcessingError(f"Normalization cancelled by user for '{input_path.name}'.")

    if proc.returncode != 0:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        err_lines = stderr_text.splitlines()[-12:] if stderr_text else ["Unknown FFmpeg error"]
        raise ProcessingError(
            f"FFmpeg normalization failed for '{input_path.name}' (exit code {proc.returncode}):\n"
            + "\n".join(err_lines)
        )

    if not temp_path.exists() or temp_path.stat().st_size == 0:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise ProcessingError(f"FFmpeg did not produce a valid output file for '{input_path.name}'.")

    return temp_path
