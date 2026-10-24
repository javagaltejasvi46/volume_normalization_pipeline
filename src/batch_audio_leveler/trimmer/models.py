"""Data models for audio trimming and segment definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class AudioSegment:
    """A single audio clip defined by start and end pointers/timestamps in seconds."""
    start_seconds: float
    end_seconds: float
    label: str = ""

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)


@dataclass
class TrimJobConfig:
    """Configuration for an audio trimming batch job."""
    source_file: Path
    segments: List[AudioSegment]
    output_dir: Path
    output_format: str = "mp3"  # "mp3" or "original"
    audio_bitrate: str = "192k"


@dataclass
class TrimResult:
    """Result summary of audio trimming execution."""
    source_file: Path
    exported_files: List[Path] = field(default_factory=list)
    failed_segments: List[str] = field(default_factory=list)
