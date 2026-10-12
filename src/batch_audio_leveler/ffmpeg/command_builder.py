"""Construction of FFmpeg subprocess argument lists."""

from __future__ import annotations

from pathlib import Path
from typing import List

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.models import AudioMeasurement, NormalizationPlan


def build_analysis_command(
    ffmpeg_path: Path,
    input_path: Path,
    stream_index: int = 0,
    target_i: float = -16.0,
    target_tp: float = -2.0,
    target_lra: float = 11.0,
) -> List[str]:
    """Build argument list for Pass 1 loudnorm measurement."""
    filter_expr = f"loudnorm=I={target_i:.1f}:TP={target_tp:.1f}:LRA={target_lra:.1f}:print_format=json"
    return [
        str(ffmpeg_path),
        "-hide_banner",
        "-nostats",
        "-i",
        str(input_path),
        "-map",
        f"0:a:{stream_index}",
        "-filter:a",
        filter_expr,
        "-f",
        "null",
        "-",
    ]


def build_loudnorm_filter_string(
    plan: NormalizationPlan,
    measurement: AudioMeasurement,
    config: AppConfig,
) -> str:
    """Build loudnorm 2-pass filter expression."""
    target_i = plan.batch_target_lufs
    target_tp = plan.true_peak_ceiling_dbtp
    target_lra = config.target_lra

    measured_i = measurement.integrated_lufs if measurement.integrated_lufs is not None else target_i
    measured_tp = measurement.true_peak_dbtp if measurement.true_peak_dbtp is not None else target_tp
    measured_lra = measurement.loudness_range_lu if measurement.loudness_range_lu is not None else target_lra
    measured_thresh = measurement.threshold_lufs if measurement.threshold_lufs is not None else -70.0
    offset = measurement.target_offset if measurement.target_offset is not None else 0.0

    linear_flag = "true" if plan.planned_mode == "linear" else "false"

    return (
        f"loudnorm=I={target_i:.1f}:TP={target_tp:.1f}:LRA={target_lra:.1f}:"
        f"measured_I={measured_i:.2f}:measured_TP={measured_tp:.2f}:"
        f"measured_LRA={measured_lra:.2f}:measured_thresh={measured_thresh:.2f}:"
        f"offset={offset:.2f}:linear={linear_flag}"
    )


def build_normalization_command(
    ffmpeg_path: Path,
    input_path: Path,
    output_path: Path,
    plan: NormalizationPlan,
    measurement: AudioMeasurement,
    config: AppConfig,
    stream_index: int = 0,
    has_subtitles: bool = False,
) -> List[str]:
    """Build argument list for Pass 2 audio normalization."""
    filter_expr = build_loudnorm_filter_string(plan, measurement, config)

    cmd = [
        str(ffmpeg_path),
        "-hide_banner",
        "-nostats",
        "-y",  # Overwrite temp file safely
        "-i",
        str(input_path),
        # Preserve original video without re-encoding
        "-map",
        "0:v?",
        "-c:v",
        "copy",
        # Map audio stream and normalize
        "-map",
        f"0:a:{stream_index}",
        "-filter:a",
        filter_expr,
        "-c:a",
        config.audio_codec,
        "-b:a",
        config.audio_bitrate,
        # Preserve chapters and container metadata
        "-map_metadata",
        "0",
        "-movflags",
        "+faststart",
    ]

    # Map subtitles if available
    if has_subtitles:
        cmd.extend(["-map", "0:s?", "-c:s", "copy"])

    cmd.append(str(output_path))
    return cmd
