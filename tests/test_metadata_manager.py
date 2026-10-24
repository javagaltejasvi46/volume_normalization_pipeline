import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from batch_audio_leveler.metadata.manager import (
    MetadataApplyResult,
    apply_metadata_from_csv,
    extract_directory_metadata,
    extract_file_tags,
    get_tag_value,
)


def test_get_tag_value():
    tags = {
        "TITLE": "Song Title",
        "artist": "Artist Name",
        "ALBUM": "Great Album",
    }
    assert get_tag_value(tags, "title") == "Song Title"
    assert get_tag_value(tags, "artist") == "Artist Name"
    assert get_tag_value(tags, "album") == "Great Album"
    assert get_tag_value(tags, "nonexistent") == ""


def test_extract_file_tags():
    mock_probe_output = {
        "format": {
            "tags": {
                "title": "Kannada Song",
                "artist": "SPB",
                "album": "Hits",
                "date": "1995",
            }
        },
        "streams": [
            {
                "codec_type": "audio",
                "tags": {
                    "genre": "Soundtrack",
                    "comment": "Restored audio",
                },
            }
        ],
    }

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.stdout = json.dumps(mock_probe_output)
        mock_run.return_value = mock_proc

        tags = extract_file_tags(Path("test.mp4"), Path("ffprobe.exe"))

        assert tags["title"] == "Kannada Song"
        assert tags["artist"] == "SPB"
        assert tags["album"] == "Hits"
        assert tags["genre"] == "Soundtrack"
        assert tags["year"] == "1995"
        assert tags["comment"] == "Restored audio"


def test_extract_directory_metadata(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "song1.mp4").touch()
    (src_dir / "song2.m4a").touch()
    (src_dir / "readme.txt").touch()

    out_csv = tmp_path / "metadata.csv"

    mock_probe_output = {
        "format": {
            "tags": {
                "title": "Sample Title",
                "artist": "Sample Artist",
            }
        },
        "streams": [],
    }

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.stdout = json.dumps(mock_probe_output)
        mock_run.return_value = mock_proc

        count = extract_directory_metadata(src_dir, out_csv, Path("ffprobe.exe"))
        assert count == 2
        assert out_csv.is_file()

        with open(out_csv, mode="r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert rows[0]["title"] == "Sample Title"
            assert rows[0]["artist"] == "Sample Artist"


def test_apply_metadata_from_csv(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "track1.mp4").write_text("dummy media content")

    out_dir = tmp_path / "dest"
    csv_file = tmp_path / "tags.csv"

    with open(csv_file, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "filename",
                "title",
                "artist",
                "album",
                "genre",
                "year",
                "track",
                "comment",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "filename": "track1.mp4",
                "title": "New Title",
                "artist": "New Artist",
                "album": "New Album",
                "genre": "Folk",
                "year": "2024",
                "track": "1",
                "comment": "Tagged",
            }
        )

    def fake_subprocess_run(cmd, **kwargs):
        # The last argument is temp output file path
        temp_out = Path(cmd[-1])
        temp_out.write_text("updated media content")
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        return res

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        result = apply_metadata_from_csv(
            csv_path=csv_file,
            source_dir=src_dir,
            output_dir=out_dir,
            ffmpeg_path=Path("ffmpeg.exe"),
        )

        assert result.total_in_csv == 1
        assert result.updated_count == 1
        assert result.skipped_count == 0
        assert result.failed_count == 0

        final_file = out_dir / "track1.mp4"
        assert final_file.is_file()
        assert final_file.read_text() == "updated media content"
