from pathlib import Path
import tempfile

from batch_audio_leveler.queue_manager import QueueManager


def test_queue_add_file_and_deduplicate(tmp_path: Path):
    f1 = tmp_path / "video1.mp4"
    f1.touch()
    f2 = tmp_path / "notes.txt"
    f2.touch()

    qm = QueueManager()
    assert len(qm) == 0

    job = qm.add_file(f1)
    assert job is not None
    assert len(qm) == 1

    # Adding non-MP4 should fail
    assert qm.add_file(f2) is None
    assert len(qm) == 1

    # Adding same file again should de-duplicate
    job2 = qm.add_file(f1)
    assert job2 == job
    assert len(qm) == 1


def test_queue_add_folder(tmp_path: Path):
    sub = tmp_path / "nested"
    sub.mkdir()
    (tmp_path / "clip1.MP4").touch()  # Case insensitivity test
    (tmp_path / "clip2.m4v").touch()
    (tmp_path / "ignore.avi").touch()
    (sub / "clip3.mp4").touch()

    qm = QueueManager()
    # Non-recursive
    count = qm.add_folder(tmp_path, recursive=False)
    assert count == 2
    assert len(qm) == 2

    # Recursive
    count_rec = qm.add_folder(tmp_path, recursive=True)
    assert count_rec == 1  # only clip3 was new
    assert len(qm) == 3


def test_queue_remove_and_clear(tmp_path: Path):
    f1 = tmp_path / "a.mp4"
    f2 = tmp_path / "b.mp4"
    f1.touch()
    f2.touch()

    qm = QueueManager()
    qm.add_file(f1)
    qm.add_file(f2)
    assert len(qm) == 2

    # Remove index 0
    assert qm.remove_index(0) is True
    assert len(qm) == 1
    assert qm.jobs[0].path == f2

    # Clear
    qm.clear()
    assert len(qm) == 0
