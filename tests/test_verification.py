from pathlib import Path
from unittest.mock import patch

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.ffmpeg.verifier import verify_normalized_file
from batch_audio_leveler.models import AudioMeasurement, NormalizationPlan


def test_verify_within_tolerances():
    config = AppConfig(
        ffmpeg_path=Path("ffmpeg.exe"),
        loudness_tolerance_lu=1.5,
        peak_tolerance_dbtp=0.5,
    )
    plan = NormalizationPlan(
        path=Path("sample.mp4"),
        batch_target_lufs=-16.0,
        requested_gain_db=4.0,
        planned_mode="linear",
        true_peak_ceiling_dbtp=-2.0,
        expected_target_reachable=True,
    )
    mock_after = AudioMeasurement(
        path=Path("out.mp4"),
        integrated_lufs=-16.3,  # diff 0.3 <= 1.5
        true_peak_dbtp=-2.1,   # <= -2.0 + 0.5
        measurement_valid=True,
    )

    with patch("batch_audio_leveler.ffmpeg.verifier.measure_file_loudness", return_value=mock_after):
        res, warns = verify_normalized_file(Path("out.mp4"), plan, config)
        assert res.integrated_lufs == -16.3
        assert len(warns) == 0


def test_verify_warns_on_loudness_deviation():
    config = AppConfig(
        ffmpeg_path=Path("ffmpeg.exe"),
        loudness_tolerance_lu=1.0,
        peak_tolerance_dbtp=0.5,
    )
    plan = NormalizationPlan(
        path=Path("sample.mp4"),
        batch_target_lufs=-16.0,
        requested_gain_db=4.0,
        planned_mode="linear",
        true_peak_ceiling_dbtp=-2.0,
        expected_target_reachable=True,
    )
    mock_after = AudioMeasurement(
        path=Path("out.mp4"),
        integrated_lufs=-18.0,  # diff 2.0 > 1.0
        true_peak_dbtp=-2.0,
        measurement_valid=True,
    )

    with patch("batch_audio_leveler.ffmpeg.verifier.measure_file_loudness", return_value=mock_after):
        res, warns = verify_normalized_file(Path("out.mp4"), plan, config)
        assert len(warns) == 1
        assert "differs from target" in warns[0]


def test_verify_warns_on_peak_violation():
    config = AppConfig(
        ffmpeg_path=Path("ffmpeg.exe"),
        loudness_tolerance_lu=1.5,
        peak_tolerance_dbtp=0.5,
    )
    plan = NormalizationPlan(
        path=Path("sample.mp4"),
        batch_target_lufs=-16.0,
        requested_gain_db=4.0,
        planned_mode="linear",
        true_peak_ceiling_dbtp=-2.0,
        expected_target_reachable=True,
    )
    mock_after = AudioMeasurement(
        path=Path("out.mp4"),
        integrated_lufs=-16.0,
        true_peak_dbtp=-1.2,  # > -2.0 + 0.5 = -1.5
        measurement_valid=True,
    )

    with patch("batch_audio_leveler.ffmpeg.verifier.measure_file_loudness", return_value=mock_after):
        res, warns = verify_normalized_file(Path("out.mp4"), plan, config)
        assert len(warns) == 1
        assert "exceeded ceiling" in warns[0]
