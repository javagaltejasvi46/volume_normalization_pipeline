from pathlib import Path

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.models import AudioMeasurement
from batch_audio_leveler.normalization.planner import plan_file_normalization


def test_planner_linear_unconstrained():
    m = AudioMeasurement(
        path=Path("sample.mp4"),
        integrated_lufs=-20.0,
        true_peak_dbtp=-6.0,
        measurement_valid=True,
    )
    config = AppConfig(
        true_peak_ceiling_dbtp=-2.0,
        max_gain_up_db=12.0,
        max_gain_down_db=-15.0,
        allow_dynamic=False,
    )
    plan = plan_file_normalization(m, target_lufs=-16.0, config=config)

    assert plan.requested_gain_db == 4.0
    assert plan.effective_gain_db == 4.0
    assert plan.planned_mode == "linear"
    assert plan.estimated_output_peak_dbtp == -2.0
    assert plan.peak_constraint_applied is False
    assert plan.expected_target_reachable is True
    assert len(plan.warnings) == 0


def test_planner_peak_constrained_linear_mode():
    m = AudioMeasurement(
        path=Path("sample.mp4"),
        integrated_lufs=-24.0,
        true_peak_dbtp=-3.0,
        measurement_valid=True,
    )
    # Target -16 LUFS -> nominal gain = +8 dB
    # True peak -3.0 + 8.0 = +5.0 dBTP, which violates ceiling -2.0 dBTP!
    # Max allowed gain = -2.0 - (-3.0) = +1.0 dB
    config = AppConfig(
        true_peak_ceiling_dbtp=-2.0,
        allow_dynamic=False,
    )
    plan = plan_file_normalization(m, target_lufs=-16.0, config=config)

    assert plan.requested_gain_db == 8.0
    assert plan.effective_gain_db == 1.0
    assert plan.planned_mode == "linear"
    assert plan.peak_constraint_applied is True
    assert plan.expected_target_reachable is False
    assert any("Peak ceiling constraint" in w for w in plan.warnings)


def test_planner_peak_constrained_dynamic_mode():
    m = AudioMeasurement(
        path=Path("sample.mp4"),
        integrated_lufs=-24.0,
        true_peak_dbtp=-3.0,
        measurement_valid=True,
    )
    config = AppConfig(
        true_peak_ceiling_dbtp=-2.0,
        allow_dynamic=True,
    )
    plan = plan_file_normalization(m, target_lufs=-16.0, config=config)

    assert plan.requested_gain_db == 8.0
    assert plan.planned_mode == "dynamic"
    assert plan.peak_constraint_applied is True
    assert plan.expected_target_reachable is True
    assert any("dynamic loudnorm mode" in w for w in plan.warnings)


def test_planner_gain_limits():
    m = AudioMeasurement(
        path=Path("sample.mp4"),
        integrated_lufs=-35.0,
        true_peak_dbtp=-15.0,
        measurement_valid=True,
    )
    # Target -16 LUFS -> nominal gain = +19 dB, max up is 10 dB
    config = AppConfig(
        max_gain_up_db=10.0,
        true_peak_ceiling_dbtp=-1.0,
    )
    plan = plan_file_normalization(m, target_lufs=-16.0, config=config)

    assert plan.requested_gain_db == 19.0
    assert plan.effective_gain_db == 10.0
    assert any("Gain boost limited" in w for w in plan.warnings)


def test_planner_silent_file():
    m = AudioMeasurement(
        path=Path("silent.mp4"),
        integrated_lufs=None,
        true_peak_dbtp=None,
        measurement_valid=False,
        is_silent=True,
    )
    config = AppConfig()
    plan = plan_file_normalization(m, target_lufs=-16.0, config=config)

    assert plan.planned_mode == "skip"
    assert plan.expected_target_reachable is False
    assert any("silent" in w for w in plan.warnings)
