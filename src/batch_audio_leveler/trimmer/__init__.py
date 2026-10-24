"""Audio trimming, segment slicing, and timestamp parsing module."""

from batch_audio_leveler.trimmer.models import (
    AudioSegment,
    TrimJobConfig,
    TrimResult,
)
from batch_audio_leveler.trimmer.parser import (
    format_timestamp,
    parse_timestamp,
    sanitize_filename_part,
)
from batch_audio_leveler.trimmer.engine import trim_audio_segments

__all__ = [
    "AudioSegment",
    "TrimJobConfig",
    "TrimResult",
    "parse_timestamp",
    "format_timestamp",
    "sanitize_filename_part",
    "trim_audio_segments",
]
