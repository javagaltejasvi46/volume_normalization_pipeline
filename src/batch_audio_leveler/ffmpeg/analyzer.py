"""EBU R128 / ITU-R BS.1770 audio loudness measurement using FFmpeg loudnorm."""

from __future__ import annotations

import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from batch_audio_leveler.models import AudioMeasurement
from batch_audio_leveler.utils.cancellation import CancellationToken


class LoudnessAnalysisError(Exception):
    """Raised when measurement fails."""
    pass


def parse_float_metric(val: Any) -> Optional[float]:
    """Parse string/number metric, converting -inf/inf/nan to None or checking finiteness."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isinf(f) or math.isnan(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def parse_loudnorm_output(stderr_text: Optional[str], source_path: Path, stream_index: int = 0) -> AudioMeasurement:
    """Robustly parse loudnorm JSON metrics block from FFmpeg stderr."""
    now_iso = datetime.now(timezone.utc).isoformat()
    if not stderr_text:
        return AudioMeasurement(
            path=source_path,
            audio_stream_index=stream_index,
            measurement_valid=False,
            is_silent=False,
            raw_ffmpeg_json=None,
            measured_at=now_iso,
        )

    # Search for JSON object block { ... } in stderr
    # loudnorm outputs [Parsed_loudnorm_...] followed by { ... }
    json_match = re.search(r"\{\s*\"input_i\"[\s\S]*?\}", stderr_text)
    if not json_match:
        return AudioMeasurement(
            path=source_path,
            audio_stream_index=stream_index,
            measurement_valid=False,
            is_silent=False,
            raw_ffmpeg_json=None,
            measured_at=now_iso,
        )

    json_str = json_match.group(0)
    try:
        data: Dict[str, Any] = json.loads(json_str)
    except json.JSONDecodeError:
        return AudioMeasurement(
            path=source_path,
            audio_stream_index=stream_index,
            measurement_valid=False,
            is_silent=False,
            raw_ffmpeg_json=None,
            measured_at=now_iso,
        )

    raw_i = str(data.get("input_i", "")).strip().lower()
    raw_tp = str(data.get("input_tp", "")).strip().lower()

    # Check for silent input
    is_silent = False
    if "-inf" in raw_i or "-inf" in raw_tp or "nan" in raw_i:
        is_silent = True

    parsed_i = parse_float_metric(data.get("input_i"))
    parsed_tp = parse_float_metric(data.get("input_tp"))
    parsed_lra = parse_float_metric(data.get("input_lra"))
    parsed_thresh = parse_float_metric(data.get("input_thresh"))
    parsed_offset = parse_float_metric(data.get("target_offset"))

    # Audio with extremely low level (e.g. <= -70 LUFS) is considered silent/near-silent
    if parsed_i is not None and parsed_i <= -70.0:
        is_silent = True

    # Valid measurement requires parsed integrated LUFS and true peak
    measurement_valid = (not is_silent) and (parsed_i is not None) and (parsed_tp is not None)

    return AudioMeasurement(
        path=source_path,
        audio_stream_index=stream_index,
        integrated_lufs=parsed_i,
        true_peak_dbtp=parsed_tp,
        loudness_range_lu=parsed_lra,
        threshold_lufs=parsed_thresh,
        target_offset=parsed_offset,
        measurement_valid=measurement_valid,
        is_silent=is_silent,
        raw_ffmpeg_json=data,
        measured_at=now_iso,
    )


def measure_file_loudness(
    file_path: Path,
    ffmpeg_path: Path,
    stream_index: int = 0,
    target_i: float = -16.0,
    target_tp: float = -2.0,
    target_lra: float = 11.0,
    timeout_seconds: int = 600,
    cancellation_token: Optional[CancellationToken] = None,
) -> AudioMeasurement:
    """Run FFmpeg loudnorm measurement pass on a file and return parsed AudioMeasurement."""
    if not file_path.is_file():
        raise LoudnessAnalysisError(f"Input file not found: {file_path}")

    # Build measurement command
    # Filter loudnorm with print_format=json directed to null muxer
    filter_expr = f"loudnorm=I={target_i:.1f}:TP={target_tp:.1f}:LRA={target_lra:.1f}:print_format=json"

    cmd = [
        str(ffmpeg_path),
        "-hide_banner",
        "-nostats",
        "-i",
        str(file_path),
        "-map",
        f"0:a:{stream_index}",
        "-filter:a",
        filter_expr,
        "-f",
        "null",
        "-",
    ]

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
        raise LoudnessAnalysisError(f"Failed to spawn FFmpeg for '{file_path}': {e}") from e

    if cancellation_token:
        cancellation_token.register_process(proc)

    try:
        stdout_text, stderr_text = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as e:
        proc.kill()
        proc.communicate()
        raise LoudnessAnalysisError(f"Loudness measurement timed out after {timeout_seconds}s for '{file_path}'.") from e
    finally:
        if cancellation_token:
            cancellation_token.unregister_process()

    if cancellation_token and cancellation_token.is_cancelled:
        raise LoudnessAnalysisError(f"Loudness measurement cancelled by user for '{file_path}'.")

    stderr_text = stderr_text or ""
    if proc.returncode != 0:
        error_excerpt = "\n".join(stderr_text.splitlines()[-10:]) if stderr_text else "Unknown FFmpeg error"
        raise LoudnessAnalysisError(
            f"FFmpeg loudness measurement failed (exit code {proc.returncode}) for '{file_path}':\n{error_excerpt}"
        )

    return parse_loudnorm_output(stderr_text, file_path, stream_index)
