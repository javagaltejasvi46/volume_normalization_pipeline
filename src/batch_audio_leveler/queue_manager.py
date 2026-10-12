"""Batch queue management, file discovery, and de-duplication."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Union

from batch_audio_leveler.models import FileJob, JobStatus
from batch_audio_leveler.utils.paths import clean_path, is_mp4_file


class QueueManager:
    """Manages queued media files and ensures idempotent, de-duplicated tracking."""

    def __init__(self) -> None:
        self._jobs: Dict[Path, FileJob] = {}

    @property
    def jobs(self) -> List[FileJob]:
        return list(self._jobs.values())

    def __len__(self) -> int:
        return len(self._jobs)

    def add_file(self, raw_path: Union[str, Path]) -> Optional[FileJob]:
        """Add a single MP4 file if valid and not already queued."""
        path = clean_path(raw_path)
        if not path.is_file():
            return None
        if not is_mp4_file(path):
            return None

        # De-duplicate by canonical resolved path
        if path in self._jobs:
            return self._jobs[path]

        job = FileJob(path=path)
        self._jobs[path] = job
        return job

    def add_folder(self, raw_folder: Union[str, Path], recursive: bool = False) -> int:
        """Scan a directory for MP4 files and add them to the queue."""
        folder = clean_path(raw_folder)
        if not folder.is_dir():
            return 0

        added_count = 0
        if recursive:
            pattern_gen = folder.rglob("*")
        else:
            pattern_gen = folder.glob("*")

        for entry in sorted(pattern_gen):
            if entry.is_file() and is_mp4_file(entry):
                if entry not in self._jobs:
                    self._jobs[entry] = FileJob(path=entry)
                    added_count += 1

        return added_count

    def remove_index(self, index: int) -> bool:
        """Remove file by 0-based list index."""
        jobs_list = self.jobs
        if 0 <= index < len(jobs_list):
            target = jobs_list[index].path
            if target in self._jobs:
                del self._jobs[target]
                return True
        return False

    def remove_path(self, path: Path) -> bool:
        """Remove file by path."""
        target = clean_path(path)
        if target in self._jobs:
            del self._jobs[target]
            return True
        return False

    def clear(self) -> None:
        """Clear all queued items."""
        self._jobs.clear()

    def reset_analysis(self) -> None:
        """Reset measurement, plan, and result states for all items."""
        for job in self._jobs.values():
            job.measurement = None
            job.plan = None
            job.result = None
