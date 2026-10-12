import subprocess
from pathlib import Path
import pytest

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.ffmpeg.analyzer import measure_file_loudness
from batch_audio_leveler.ffmpeg.discovery import discover_ffmpeg
from batch_audio_leveler.ffmpeg.probe import probe_file
from batch_audio_leveler.ffmpeg.processor import process_file_normalization
from batch_audio_leveler.ffmpeg.verifier import verify_normalized_file
from batch_audio_leveler.normalization.planner import plan_file_normalization


env = discover_ffmpeg()
pytestmark = pytest.mark.skipif(
    not env.is_ready,
    reason=f"FFmpeg or FFprobe not available or missing loudnorm: {env.ffmpeg.error_message}",
)


@pytest.fixture(scope="module")
def synthetic_mp4(tmp_path_factory) -> Path:
    """Generate a 3-second synthetic MP4 video with audio."""
    temp_dir = tmp_path_factory.mktemp("media")
    input_video = temp_dir / "synthetic_test.mp4"

    cmd = [
        str(env.ffmpeg.path),
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=320x240:rate=25:duration=3",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=3",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(input_video),
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert input_video.exists()
    return input_video


def test_full_ffmpeg_pipeline(synthetic_mp4: Path, tmp_path: Path):
    orig_stat = synthetic_mp4.stat()
    orig_size = orig_stat.st_size
    orig_mtime = orig_stat.st_mtime

    config = AppConfig(
        ffmpeg_path=env.ffmpeg.path,
        ffprobe_path=env.ffprobe.path,
        output_dir=tmp_path / "output",
        fixed_target_lufs=-16.0,
        true_peak_ceiling_dbtp=-2.0,
    )

    # 1. Probe input
    probe_in = probe_file(synthetic_mp4, env.ffprobe.path)
    assert len(probe_in.video_streams) == 1
    assert len(probe_in.audio_streams) == 1
    assert probe_in.duration_seconds is not None
    assert abs(probe_in.duration_seconds - 3.0) < 0.5

    # 2. Pass 1: Measure loudness
    meas_in = measure_file_loudness(
        file_path=synthetic_mp4,
        ffmpeg_path=env.ffmpeg.path,
        target_i=config.fixed_target_lufs,
        target_tp=config.true_peak_ceiling_dbtp,
    )
    assert meas_in.measurement_valid is True
    assert meas_in.integrated_lufs is not None
    assert meas_in.true_peak_dbtp is not None

    # 3. Plan normalization
    plan = plan_file_normalization(meas_in, target_lufs=-16.0, config=config)
    assert plan.planned_mode in {"linear", "dynamic"}

    # 4. Pass 2: Process normalization into temp file
    final_output = config.output_dir / "normalized_synthetic.mp4"
    config.output_dir.mkdir(parents=True, exist_ok=True)

    temp_out = process_file_normalization(
        input_path=synthetic_mp4,
        final_output_path=final_output,
        plan=plan,
        measurement=meas_in,
        config=config,
    )
    assert temp_out.exists()

    # 5. Pass 3: Verification
    after_meas, warns = verify_normalized_file(
        output_path=temp_out,
        plan=plan,
        config=config,
    )
    assert after_meas.measurement_valid is True
    assert after_meas.integrated_lufs is not None

    # Commit temp file to final output
    temp_out.rename(final_output)
    assert final_output.exists()

    # 6. Probe output
    probe_out = probe_file(final_output, env.ffprobe.path)
    assert len(probe_out.video_streams) == 1
    assert len(probe_out.audio_streams) == 1
    # Video stream codec should be identical (copied)
    assert probe_out.video_streams[0]["codec_name"] == probe_in.video_streams[0]["codec_name"]
    # Output duration close to input
    assert abs(probe_out.duration_seconds - probe_in.duration_seconds) < 0.5
    # Measured output loudness close to target
    assert abs(after_meas.integrated_lufs - (-16.0)) < 2.0

    # 7. Verify original input was untouched
    after_stat = synthetic_mp4.stat()
    assert after_stat.st_size == orig_size
    assert after_stat.st_mtime == orig_mtime


def test_kannada_unicode_filename_measurement(synthetic_mp4: Path, tmp_path: Path):
    """Verify that FFmpeg measurement and processing work on Kannada Unicode paths."""
    kannada_file = tmp_path / "ಈ ಹಸಿರು ಸಿರಿಯಲಿ.mp4"
    kannada_file.write_bytes(synthetic_mp4.read_bytes())

    probe_res = probe_file(kannada_file, env.ffprobe.path)
    assert len(probe_res.audio_streams) >= 1

    meas = measure_file_loudness(
        file_path=kannada_file,
        ffmpeg_path=env.ffmpeg.path,
    )
    assert meas.measurement_valid is True
    assert meas.integrated_lufs is not None
