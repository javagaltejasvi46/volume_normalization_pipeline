"""Batch median and fixed target calculation."""

from __future__ import annotations

import statistics
from typing import List, Optional

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.models import AudioMeasurement, NormalizationMode


class TargetCalculationError(Exception):
    """Raised when target cannot be calculated."""
    pass


def calculate_batch_target(
    measurements: List[AudioMeasurement],
    config: AppConfig,
) -> float:
    """Calculate batch integrated LUFS target.

    For BATCH_MEDIAN mode:
      Filters valid non-silent measurements and computes the median.
    For FIXED mode:
      Returns config.fixed_target_lufs.
    """
    if config.mode == NormalizationMode.FIXED:
        return round(config.fixed_target_lufs, 2)

    valid_values: List[float] = [
        m.integrated_lufs
        for m in measurements
        if m.measurement_valid
        and not m.is_silent
        and m.integrated_lufs is not None
    ]

    if not valid_values:
        raise TargetCalculationError(
            "Cannot calculate batch median: no valid, non-silent audio measurements were found. "
            "Please check source files or use Fixed Target mode."
        )

    median_val = statistics.median(valid_values)
    return round(float(median_val), 2)
