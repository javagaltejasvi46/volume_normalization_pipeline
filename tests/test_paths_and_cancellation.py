from pathlib import Path
import time
import subprocess
import sys

from batch_audio_leveler.utils.cancellation import CancellationToken
from batch_audio_leveler.utils.paths import (
    clean_path,
    ensure_directory,
    get_temp_output_path,
    get_unique_output_path,
    is_mp4_file,
)


def test_clean_path_with_quotes_and_spaces():
    p = clean_path('  "C:/sample path with spaces/video.mp4"  ')
    assert "sample path with spaces" in str(p)


def test_unique_output_path_incrementing(tmp_path: Path):
    source = tmp_path / "song.mp4"
    source.touch()
    out_dir = tmp_path / "out"

    # 1. Output doesn't exist
    target1 = get_unique_output_path(out_dir, source, overwrite=False)
    assert target1.name == "song.mp4"
    target1.touch()

    # 2. Output exists, overwrite=False -> song_1.mp4
    target2 = get_unique_output_path(out_dir, source, overwrite=False)
    assert target2.name == "song_1.mp4"
    target2.touch()

    # 3. Next -> song_2.mp4
    target3 = get_unique_output_path(out_dir, source, overwrite=False)
    assert target3.name == "song_2.mp4"

    # 4. overwrite=True returns base song.mp4
    target_over = get_unique_output_path(out_dir, source, overwrite=True)
    assert target_over.name == "song.mp4"


def test_unicode_paths(tmp_path: Path):
    unicode_dir = tmp_path / "日本語_musique_éè"
    unicode_dir.mkdir()
    f = unicode_dir / "vidéo_test_🎶.mp4"
    f.touch()

    assert is_mp4_file(f) is True
    cleaned = clean_path(f)
    assert cleaned.exists()

    temp_p = get_temp_output_path(f)
    assert ".tmp_" in temp_p.name


def test_cancellation_token():
    token = CancellationToken()
    assert token.is_cancelled is False

    # Spawn a sleeping python process
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        shell=False,
    )
    token.register_process(proc)
    assert proc.poll() is None

    # Cancel token
    token.cancel()
    assert token.is_cancelled is True

    # Give OS a moment to terminate
    time.sleep(0.3)
    assert proc.poll() is not None
    token.unregister_process()
