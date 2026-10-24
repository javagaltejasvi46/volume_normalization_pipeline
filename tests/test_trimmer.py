from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from batch_audio_leveler.trimmer.models import AudioSegment, TrimJobConfig
from batch_audio_leveler.trimmer.parser import (
    format_timestamp,
    parse_timestamp,
    sanitize_filename_part,
)
from batch_audio_leveler.trimmer.engine import trim_audio_segments


def test_parse_timestamp_seconds():
    assert parse_timestamp(90) == 90.0
    assert parse_timestamp(90.5) == 90.5
    assert parse_timestamp("90") == 90.0
    assert parse_timestamp("90s") == 90.0
    assert parse_timestamp("90.5s") == 90.5


def test_parse_timestamp_mmss():
    assert parse_timestamp("01:30") == 90.0
    assert parse_timestamp("1:30") == 90.0
    assert parse_timestamp("00:45") == 45.0
    assert parse_timestamp("00:00") == 0.0


def test_parse_timestamp_hhmmss():
    assert parse_timestamp("01:00:00") == 3600.0
    assert parse_timestamp("01:01:30") == 3690.0
    assert parse_timestamp("00:01:30") == 90.0


def test_parse_timestamp_descriptive():
    assert parse_timestamp("1m 30s") == 90.0
    assert parse_timestamp("1h 15m") == 4500.0
    assert parse_timestamp("45s") == 45.0


def test_parse_timestamp_invalid():
    with pytest.raises(ValueError):
        parse_timestamp("")
    with pytest.raises(ValueError):
        parse_timestamp(-10)
    with pytest.raises(ValueError):
        parse_timestamp("-01:30")
    with pytest.raises(ValueError):
        parse_timestamp("invalid_text")


def test_format_timestamp():
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(90) == "01:30"
    assert format_timestamp(3690) == "01:01:30"


def test_sanitize_filename_part():
    assert sanitize_filename_part("01:30 to 02:45") == "01-30_to_02-45"
    assert sanitize_filename_part("My Chorus / Hook?") == "My_Chorus_-_Hook"


def test_trim_audio_segments_mocked(tmp_path: Path):
    src = tmp_path / "song.mp3"
    src.write_text("dummy audio")
    out_dir = tmp_path / "trimmed"

    cfg = TrimJobConfig(
        source_file=src,
        segments=[
            AudioSegment(start_seconds=10.0, end_seconds=30.0, label="intro"),
            AudioSegment(start_seconds=60.0, end_seconds=90.0, label="verse"),
        ],
        output_dir=out_dir,
        output_format="mp3",
    )

    def fake_run(cmd, **kwargs):
        # cmd[-1] is output path
        out_file = Path(cmd[-1])
        out_file.write_text("clip content")
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        return res

    with patch("subprocess.run", side_effect=fake_run):
        res = trim_audio_segments(
            config=cfg,
            ffmpeg_path=Path("ffmpeg.exe"),
        )
        assert len(res.exported_files) == 2
        assert len(res.failed_segments) == 0
        assert (out_dir / "song_intro.mp3").is_file()
        assert (out_dir / "song_verse.mp3").is_file()


def test_trim_audio_segments_rejects_collisions(tmp_path: Path):
    src = tmp_path / "song.mp3"
    src.write_text("dummy audio")
    out_dir = tmp_path / "trimmed"

    cfg = TrimJobConfig(
        source_file=src,
        segments=[
            AudioSegment(start_seconds=10.0, end_seconds=30.0, label="seg1"),
            AudioSegment(start_seconds=20.0, end_seconds=40.0, label="seg2"),  # collision!
        ],
        output_dir=out_dir,
    )

    with pytest.raises(ValueError, match="Cannot export clips due to segment errors"):
        trim_audio_segments(cfg, Path("ffmpeg.exe"))

