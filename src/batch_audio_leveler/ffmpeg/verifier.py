"""Verification pass: post-processing loudness and peak measurement."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.ffmpeg.analyzer import measure_file_loudness
from batch_audio_leveler.models import AudioMeasurement, NormalizationPlan
from batch_audio_leveler.utils.cancellation import CancellationToken


class VerificationError(Exception):
    """Raised when verification fails."""
    pass


def verify_normalized_file(
    output_path: Path,
    plan: NormalizationPlan,
    config: AppConfig,
    stream_index: int = 0,
    cancellation_token: Optional[CancellationToken] = None,
) -> Tuple[AudioMeasurement, List[str]]:
    """Measure the exported output file and verify against loudness and peak tolerances."""
    if not config.ffmpeg_path:
        raise VerificationError("FFmpeg path not configured.")

    warnings: List[str] = []
    measurement = measure_file_loudness(
        file_path=output_path,
        ffmpeg_path=config.ffmpeg_path,
        stream_index=stream_index,
        target_i=plan.batch_target_lufs,
        target_tp=plan.true_peak_ceiling_dbtp,
        target_lra=config.target_lra,
        timeout_seconds=config.timeout_seconds,
        cancellation_token=cancellation_token,
    )

    if not measurement.measurement_valid or measurement.integrated_lufs is None:
        warnings.append("Verification pass: unable to obtain valid loudness measurement from output.")
        return measurement, warnings

    target_lufs = plan.batch_target_lufs
    measured_lufs = measurement.integrated_lufs
    lufs_diff = abs(measured_lufs - target_lufs)

    # Check loudness tolerance
    if plan.expected_target_reachable and lufs_diff > config.loudness_tolerance_lu:
        warnings.append(
            f"Achieved loudness ({measured_lufs:.1f} LUFS) differs from target ({target_lufs:.1f} LUFS) "
            f"by {lufs_diff:.1f} LU (tolerance: ±{config.loudness_tolerance_lu:.1f} LU)."
        )

    # Check true peak tolerance
    ceiling = plan.true_peak_ceiling_dbtp
    if measurement.true_peak_dbtp is not None:
        measured_tp = measurement.true_peak_dbtp
        if measured_tp > (ceiling + config.peak_tolerance_dbtp):
            warnings.append(
                f"Achieved true peak ({measured_tp:+.1f} dBTP) exceeded ceiling ({ceiling:.1f} dBTP) "
                f"by {measured_tp - ceiling:+.1f} dBTP."
            )

    return measurement, warnings
