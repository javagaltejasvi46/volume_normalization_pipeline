"""Normalization planning and true-peak feasibility engine."""

from __future__ import annotations

from typing import List

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.models import AudioMeasurement, NormalizationPlan


def plan_file_normalization(
    measurement: AudioMeasurement,
    target_lufs: float,
    config: AppConfig,
) -> NormalizationPlan:
    """Generate a NormalizationPlan for a single file measurement."""
    path = measurement.path
    warnings: List[str] = []

    if not measurement.measurement_valid or measurement.integrated_lufs is None:
        if measurement.is_silent:
            warnings.append("Audio is silent or near-silent; normalization cannot be applied.")
        else:
            warnings.append("Invalid or missing audio loudness measurement.")

        return NormalizationPlan(
            path=path,
            batch_target_lufs=target_lufs,
            requested_gain_db=0.0,
            planned_mode="skip",
            true_peak_ceiling_dbtp=config.true_peak_ceiling_dbtp,
            estimated_output_peak_dbtp=measurement.true_peak_dbtp,
            peak_constraint_applied=False,
            expected_target_reachable=False,
            effective_gain_db=0.0,
            warnings=warnings,
        )

    nominal_gain = round(target_lufs - measurement.integrated_lufs, 2)
    effective_gain = nominal_gain

    # Apply gain-up limit
    if effective_gain > config.max_gain_up_db:
        warnings.append(
            f"Gain boost limited: requested {nominal_gain:+.1f} dB exceeds maximum limit of +{config.max_gain_up_db:.1f} dB."
        )
        effective_gain = config.max_gain_up_db

    # Apply gain-down limit
    if effective_gain < config.max_gain_down_db:
        warnings.append(
            f"Gain attenuation limited: requested {nominal_gain:+.1f} dB exceeds maximum reduction limit of {config.max_gain_down_db:.1f} dB."
        )
        effective_gain = config.max_gain_down_db

    source_tp = measurement.true_peak_dbtp
    estimated_peak = round(source_tp + effective_gain, 2) if source_tp is not None else None
    ceiling = config.true_peak_ceiling_dbtp

    planned_mode = "linear"
    peak_constraint_applied = False
    expected_reachable = (effective_gain == nominal_gain)

    if estimated_peak is not None and estimated_peak > ceiling:
        peak_constraint_applied = True
        if config.allow_dynamic:
            planned_mode = "dynamic"
            warnings.append(
                f"Peak limit would be exceeded ({estimated_peak:+.1f} dBTP > {ceiling:.1f} dBTP). "
                f"Using dynamic loudnorm mode with limiting."
            )
            expected_reachable = True
            estimated_peak = ceiling
        else:
            planned_mode = "linear"
            max_allowed_gain = round(ceiling - source_tp, 2)
            if max_allowed_gain < effective_gain:
                effective_gain = max_allowed_gain
                estimated_peak = ceiling
                expected_reachable = False
                warnings.append(
                    f"Peak ceiling constraint: gain capped from {nominal_gain:+.1f} dB to {effective_gain:+.1f} dB "
                    f"to keep true peak <= {ceiling:.1f} dBTP without dynamic compression."
                )

    return NormalizationPlan(
        path=path,
        batch_target_lufs=target_lufs,
        requested_gain_db=nominal_gain,
        planned_mode=planned_mode,
        true_peak_ceiling_dbtp=ceiling,
        estimated_output_peak_dbtp=estimated_peak,
        peak_constraint_applied=peak_constraint_applied,
        expected_target_reachable=expected_reachable,
        effective_gain_db=effective_gain,
        warnings=warnings,
    )
