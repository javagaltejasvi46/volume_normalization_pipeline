"""Segment collision detection and validation for audio trimming."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from batch_audio_leveler.trimmer.models import AudioSegment
from batch_audio_leveler.trimmer.parser import format_timestamp


@dataclass
class SegmentCollision:
    """Describes an overlap/collision between two audio segments."""
    index_a: int
    index_b: int
    seg_a: AudioSegment
    seg_b: AudioSegment
    overlap_start: float
    overlap_end: float

    @property
    def overlap_duration(self) -> float:
        return max(0.0, self.overlap_end - self.overlap_start)

    def description(self) -> str:
        s_fmt = format_timestamp(self.overlap_start)
        e_fmt = format_timestamp(self.overlap_end)
        name_a = f"Segment {self.index_a + 1}" + (f" ('{self.seg_a.label}')" if self.seg_a.label else "")
        name_b = f"Segment {self.index_b + 1}" + (f" ('{self.seg_b.label}')" if self.seg_b.label else "")
        return (
            f"{name_a} [{format_timestamp(self.seg_a.start_seconds)} - {format_timestamp(self.seg_a.end_seconds)}] "
            f"collides with {name_b} [{format_timestamp(self.seg_b.start_seconds)} - {format_timestamp(self.seg_b.end_seconds)}] "
            f"(overlap: {s_fmt} to {e_fmt}, {self.overlap_duration:.1f}s)"
        )


def find_segment_collisions(segments: List[AudioSegment]) -> List[SegmentCollision]:
    """Scan all segments and detect time overlaps."""
    collisions: List[SegmentCollision] = []
    n = len(segments)
    for i in range(n):
        for j in range(i + 1, n):
            a = segments[i]
            b = segments[j]
            overlap_s = max(a.start_seconds, b.start_seconds)
            overlap_e = min(a.end_seconds, b.end_seconds)
            # Only consider overlap if duration is strictly positive (> 0.05s tolerance)
            if overlap_e - overlap_s > 0.05:
                collisions.append(
                    SegmentCollision(
                        index_a=i,
                        index_b=j,
                        seg_a=a,
                        seg_b=b,
                        overlap_start=overlap_s,
                        overlap_end=overlap_e,
                    )
                )
    return collisions


def validate_segments_for_export(
    segments: List[AudioSegment], total_duration: Optional[float] = None
) -> List[str]:
    """Return a list of validation error strings if any pointers are invalid or colliding."""
    errors: List[str] = []
    if not segments:
        errors.append("No audio segments have been added to export.")
        return errors

    for idx, seg in enumerate(segments, 1):
        if seg.start_seconds < 0:
            errors.append(f"Segment {idx} start time cannot be negative ({seg.start_seconds}s).")
        if seg.end_seconds <= seg.start_seconds:
            errors.append(
                f"Segment {idx} end time ({format_timestamp(seg.end_seconds)}) "
                f"must be greater than start time ({format_timestamp(seg.start_seconds)})."
            )
        if total_duration and seg.end_seconds > total_duration + 0.5:
            errors.append(
                f"Segment {idx} end time ({format_timestamp(seg.end_seconds)}) "
                f"exceeds file duration ({format_timestamp(total_duration)})."
            )

    collisions = find_segment_collisions(segments)
    for c in collisions:
        errors.append(c.description())

    return errors
