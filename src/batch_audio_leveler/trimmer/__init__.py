"""Audio trimming, segment slicing, waveform visualization, and collision detection module."""

from batch_audio_leveler.trimmer.collisions import (
    SegmentCollision,
    find_segment_collisions,
    validate_segments_for_export,
)
from batch_audio_leveler.trimmer.engine import (
    probe_audio_duration,
    trim_audio_segments,
)
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
from batch_audio_leveler.trimmer.waveform import (
    extract_waveform_envelope,
    render_ascii_waveform,
)

__all__ = [
    "AudioSegment",
    "TrimJobConfig",
    "TrimResult",
    "SegmentCollision",
    "find_segment_collisions",
    "validate_segments_for_export",
    "parse_timestamp",
    "format_timestamp",
    "sanitize_filename_part",
    "probe_audio_duration",
    "trim_audio_segments",
    "extract_waveform_envelope",
    "render_ascii_waveform",
]
