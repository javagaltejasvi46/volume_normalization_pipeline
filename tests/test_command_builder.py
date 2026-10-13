from pathlib import Path

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.ffmpeg.command_builder import (
    build_analysis_command,
    build_loudnorm_filter_string,
    build_normalization_command,
)
from batch_audio_leveler.models import AudioMeasurement, NormalizationPlan


def test_build_analysis_command():
    cmd = build_analysis_command(
        ffmpeg_path=Path("ffmpeg.exe"),
        input_path=Path("my test video.mp4"),
        stream_index=1,
        target_i=-16.0,
        target_tp=-2.0,
        target_lra=11.0,
    )

    assert "ffmpeg.exe" in cmd[0]
    assert "-i" in cmd
    assert "my test video.mp4" in cmd
    assert "-map" in cmd
    assert "0:a:1" in cmd
    assert "-f" in cmd
    assert "null" in cmd


def test_build_normalization_command_copies_video():
    config = AppConfig(audio_bitrate="256k", audio_codec="aac")
    m = AudioMeasurement(
        path=Path("video with spaces.mp4"),
        integrated_lufs=-22.0,
        true_peak_dbtp=-3.5,
        loudness_range_lu=8.0,
        threshold_lufs=-32.5,
        target_offset=0.1,
        measurement_valid=True,
    )
    plan = NormalizationPlan(
        path=m.path,
        batch_target_lufs=-16.0,
        requested_gain_db=6.0,
        planned_mode="linear",
        true_peak_ceiling_dbtp=-2.0,
    )

    cmd = build_normalization_command(
        ffmpeg_path=Path("ffmpeg.exe"),
        input_path=m.path,
        output_path=Path("out_dir/video with spaces.mp4"),
        plan=plan,
        measurement=m,
        config=config,
        stream_index=0,
        has_subtitles=True,
    )

    # Verify video is copied without re-encoding
    assert "-c:v" in cmd
    c_v_idx = cmd.index("-c:v")
    assert cmd[c_v_idx + 1] == "copy"

    # Verify audio encoding
    assert "-c:a" in cmd
    c_a_idx = cmd.index("-c:a")
    assert cmd[c_a_idx + 1] == "aac"
    assert "-b:a" in cmd
    b_a_idx = cmd.index("-b:a")
    assert cmd[b_a_idx + 1] == "256k"

    # Verify subtitle mapping
    assert "-c:s" in cmd
    c_s_idx = cmd.index("-c:s")
    assert cmd[c_s_idx + 1] == "copy"

    # Verify loudnorm linear string
    filter_arg = cmd[cmd.index("-filter:a") + 1]
    assert "linear=true" in filter_arg
    assert "measured_I=-22.00" in filter_arg
    assert "measured_TP=-3.50" in filter_arg


def test_dynamic_filter_string():
    config = AppConfig()
    m = AudioMeasurement(
        path=Path("audio_ñ_unicode.mp4"),
        integrated_lufs=-20.0,
        true_peak_dbtp=-1.0,
        loudness_range_lu=5.0,
        threshold_lufs=-30.0,
        target_offset=0.0,
        measurement_valid=True,
    )
    plan = NormalizationPlan(
        path=m.path,
        batch_target_lufs=-16.0,
        requested_gain_db=4.0,
        planned_mode="dynamic",
        true_peak_ceiling_dbtp=-2.0,
    )

    f_str = build_loudnorm_filter_string(plan, m, config)
    assert "linear=false" in f_str
    assert "I=-16.0" in f_str
    assert "TP=-2.0" in f_str


def test_sanitization_of_positive_loudnorm_parameters():
    # If positive numbers slip through
    cmd = build_analysis_command(
        ffmpeg_path=Path("ffmpeg.exe"),
        input_path=Path("test.mp4"),
        target_i=15.0,
        target_tp=2.0,
    )
    filter_arg = cmd[cmd.index("-filter:a") + 1]
    assert "I=-15.0" in filter_arg
    assert "TP=-2.0" in filter_arg
