import pytest
from batch_audio_leveler.trimmer.collisions import (
    find_segment_collisions,
    validate_segments_for_export,
)
from batch_audio_leveler.trimmer.models import AudioSegment
from batch_audio_leveler.trimmer.waveform import render_ascii_waveform


def test_find_segment_collisions_clean():
    # Segments that do not overlap
    segs = [
        AudioSegment(start_seconds=0.0, end_seconds=10.0, label="intro"),
        AudioSegment(start_seconds=12.0, end_seconds=20.0, label="verse"),
        AudioSegment(start_seconds=20.0, end_seconds=30.0, label="chorus"),  # touching boundary is allowed
    ]
    collisions = find_segment_collisions(segs)
    assert len(collisions) == 0

    errors = validate_segments_for_export(segs, total_duration=40.0)
    assert len(errors) == 0


def test_find_segment_collisions_overlap():
    # Segments with overlap
    segs = [
        AudioSegment(start_seconds=10.0, end_seconds=30.0, label="part1"),
        AudioSegment(start_seconds=25.0, end_seconds=45.0, label="part2"),
    ]
    collisions = find_segment_collisions(segs)
    assert len(collisions) == 1
    assert collisions[0].overlap_start == 25.0
    assert collisions[0].overlap_end == 30.0
    assert collisions[0].overlap_duration == 5.0
    assert "part1" in collisions[0].description()
    assert "part2" in collisions[0].description()

    errors = validate_segments_for_export(segs, total_duration=50.0)
    assert any("collides" in e for e in errors)


def test_validate_segments_invalid_times():
    segs = [
        AudioSegment(start_seconds=30.0, end_seconds=10.0),  # end <= start
        AudioSegment(start_seconds=-5.0, end_seconds=15.0),  # start < 0
    ]
    errors = validate_segments_for_export(segs, total_duration=60.0)
    assert len(errors) >= 2


def test_render_ascii_waveform_with_collisions():
    amps = [0.2, 0.4, 0.8, 0.6, 0.3, 0.5, 0.9, 0.1]
    segs = [
        AudioSegment(start_seconds=0.0, end_seconds=20.0),
        AudioSegment(start_seconds=10.0, end_seconds=30.0),  # collision between 10 and 20
    ]
    output = render_ascii_waveform(
        amplitudes=amps,
        segments=segs,
        total_duration=40.0,
        width=40,
        height=3,
    )
    # Must contain collision warning markers and pointers
    assert "[bold red]" in output
    assert "Pointers:" in output
    assert "00:00" in output
