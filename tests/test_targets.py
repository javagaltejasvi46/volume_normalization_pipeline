from pathlib import Path
import pytest

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.models import AudioMeasurement, NormalizationMode
from batch_audio_leveler.normalization.targets import (
    TargetCalculationError,
    calculate_batch_target,
)


def make_measurement(path_str: str, lufs: float | None, tp: float | None = -1.0, valid: bool = True, silent: bool = False) -> AudioMeasurement:
    return AudioMeasurement(
        path=Path(path_str),
        audio_stream_index=0,
        integrated_lufs=lufs,
        true_peak_dbtp=tp,
        measurement_valid=valid,
        is_silent=silent,
    )


def test_odd_batch_median_target():
    measurements = [
        make_measurement("a.mp4", -24.0),
        make_measurement("b.mp4", -18.0),
        make_measurement("c.mp4", -14.0),
    ]
    config = AppConfig(mode=NormalizationMode.BATCH_MEDIAN)
    target = calculate_batch_target(measurements, config)
    assert target == -18.0


def test_even_batch_median_target():
    measurements = [
        make_measurement("a.mp4", -24.0),
        make_measurement("b.mp4", -20.0),
        make_measurement("c.mp4", -16.0),
        make_measurement("d.mp4", -12.0),
    ]
    config = AppConfig(mode=NormalizationMode.BATCH_MEDIAN)
    target = calculate_batch_target(measurements, config)
    # (-20 + -16) / 2 = -18.0
    assert target == -18.0


def test_fixed_target_mode():
    measurements = [
        make_measurement("a.mp4", -24.0),
    ]
    config = AppConfig(mode=NormalizationMode.FIXED, fixed_target_lufs=-14.0)
    target = calculate_batch_target(measurements, config)
    assert target == -14.0


def test_empty_batch_raises_error():
    config = AppConfig(mode=NormalizationMode.BATCH_MEDIAN)
    with pytest.raises(TargetCalculationError):
        calculate_batch_target([], config)


def test_all_invalid_batch_raises_error():
    measurements = [
        make_measurement("silent.mp4", -75.0, tp=-99.0, valid=False, silent=True),
        make_measurement("corrupt.mp4", None, tp=None, valid=False, silent=False),
    ]
    config = AppConfig(mode=NormalizationMode.BATCH_MEDIAN)
    with pytest.raises(TargetCalculationError):
        calculate_batch_target(measurements, config)


def test_mixture_excludes_invalid_and_silent():
    measurements = [
        make_measurement("valid1.mp4", -22.0),
        make_measurement("silent.mp4", None, valid=False, silent=True),
        make_measurement("valid2.mp4", -16.0),
        make_measurement("corrupt.mp4", None, valid=False, silent=False),
        make_measurement("valid3.mp4", -10.0),
    ]
    config = AppConfig(mode=NormalizationMode.BATCH_MEDIAN)
    target = calculate_batch_target(measurements, config)
    assert target == -16.0
