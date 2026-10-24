"""Audio wavegraph extraction and Rich-formatted visual waveform rendering."""

from __future__ import annotations

import math
import struct
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from batch_audio_leveler.trimmer.collisions import find_segment_collisions
from batch_audio_leveler.trimmer.models import AudioSegment
from batch_audio_leveler.trimmer.parser import format_timestamp

BLOCKS = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
SEG_COLORS = ["cyan", "green", "yellow", "magenta", "bright_blue", "white"]


def extract_waveform_envelope(
    audio_path: Path, ffmpeg_path: Path, num_bars: int = 70
) -> List[float]:
    """Fast downsampled peak envelope extraction using FFmpeg PCM pipe."""
    if not audio_path.is_file():
        return [0.1] * num_bars

    cmd = [
        str(ffmpeg_path),
        "-v",
        "quiet",
        "-i",
        str(audio_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "1000",
        "-f",
        "f32le",
        "-",
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
        raw = proc.stdout
        count = len(raw) // 4
        if count == 0:
            return [0.05] * num_bars

        # Unpack 32-bit floats
        samples = [abs(struct.unpack("f", raw[i * 4 : (i + 1) * 4])[0]) for i in range(count)]
        samples_per_bar = max(1, len(samples) // num_bars)
        bars = []
        for b in range(num_bars):
            chunk = samples[b * samples_per_bar : (b + 1) * samples_per_bar]
            bars.append(max(chunk) if chunk else 0.0)

        max_val = max(bars) if bars else 1.0
        if max_val > 0.001:
            bars = [round(min(1.0, v / max_val), 3) for v in bars]
        else:
            bars = [0.05] * num_bars

        return bars
    except Exception:
        # Fallback subtle baseline
        return [0.1] * num_bars


def render_ascii_waveform(
    amplitudes: List[float],
    segments: List[AudioSegment],
    total_duration: float,
    width: int = 70,
    height: int = 3,
    active_segment_index: Optional[int] = None,
) -> str:
    """Render a multi-row visual wavegraph with visual start/end pointers and collision highlights."""
    if total_duration <= 0:
        total_duration = 1.0

    # Ensure amplitudes match requested width
    if not amplitudes:
        amplitudes = [0.1] * width
    elif len(amplitudes) != width:
        # Resample to match width
        step = len(amplitudes) / float(width)
        resampled = []
        for i in range(width):
            src_idx = int(i * step)
            resampled.append(amplitudes[min(src_idx, len(amplitudes) - 1)])
        amplitudes = resampled

    time_per_col = total_duration / float(width)
    collisions = find_segment_collisions(segments)
    collision_intervals = [(c.overlap_start, c.overlap_end) for c in collisions]

    # Map each column to covering segments and collision status
    col_segments: List[List[int]] = []
    col_is_collision: List[bool] = []
    col_pointer_marks: List[str] = [" "] * width

    for c in range(width):
        t_start = c * time_per_col
        t_end = (c + 1) * time_per_col
        covering = []
        for s_idx, seg in enumerate(segments):
            if seg.start_seconds < t_end and seg.end_seconds > t_start:
                covering.append(s_idx)
        col_segments.append(covering)

        # Check collision in column
        has_coll = False
        if len(covering) > 1:
            has_coll = True
        else:
            for coll_s, coll_e in collision_intervals:
                if coll_s < t_end and coll_e > t_start:
                    has_coll = True
                    break
        col_is_collision.append(has_coll)

    # Place start and end markers on pointer track
    pointer_line = [" "] * width
    for s_idx, seg in enumerate(segments):
        start_c = max(0, min(width - 1, int(seg.start_seconds / time_per_col)))
        end_c = max(0, min(width - 1, int(seg.end_seconds / time_per_col)))
        label_num = str(s_idx + 1)
        color = SEG_COLORS[s_idx % len(SEG_COLORS)]

        # Fill range between start and end
        for c in range(start_c, end_c + 1):
            if col_is_collision[c]:
                pointer_line[c] = "[bold red]![/bold red]"
            elif pointer_line[c] == " ":
                pointer_line[c] = f"[{color}]━[/{color}]"

        # Start bracket
        if col_is_collision[start_c]:
            pointer_line[start_c] = f"[bold red][{label_num}[/bold red]"
        else:
            pointer_line[start_c] = f"[bold {color}][{label_num}[/bold {color}]"

        # End bracket
        if col_is_collision[end_c]:
            pointer_line[end_c] = f"[bold red]{label_num}][/bold red]"
        else:
            pointer_line[end_c] = f"[bold {color}]{label_num}][/{color}]"

    # Render waveform amplitude rows
    waveform_rows: List[str] = []
    for r in range(height - 1, -1, -1):
        line_chars: List[str] = []
        low = r / float(height)
        high = (r + 1) / float(height)
        step = (high - low) / 8.0

        for c in range(width):
            amp = amplitudes[c]
            if amp <= low:
                char = " "
            elif amp >= high:
                char = "█"
            else:
                idx = int((amp - low) / step)
                idx = max(1, min(8, idx))
                char = BLOCKS[idx]

            # Determine color for this column
            if col_is_collision[c]:
                line_chars.append(f"[bold red]{char}[/bold red]")
            elif col_segments[c]:
                s_idx = col_segments[c][0]
                color = SEG_COLORS[s_idx % len(SEG_COLORS)]
                line_chars.append(f"[{color}]{char}[/{color}]")
            else:
                line_chars.append(f"[#475569]{char}[/#475569]")

        waveform_rows.append("".join(line_chars))

    # Render Timeline Ruler
    t_start_fmt = "00:00"
    t_mid_fmt = format_timestamp(total_duration / 2.0)
    t_end_fmt = format_timestamp(total_duration)

    ruler_line = list("├" + ("─" * (width - 2)) + "┤")
    mid_pos = width // 2
    if 0 <= mid_pos < width:
        ruler_line[mid_pos] = "┼"
    ruler_str = "[dim #64748b]" + "".join(ruler_line) + "[/dim #64748b]"

    # Timestamp text line
    time_space_1 = max(1, mid_pos - len(t_start_fmt) - (len(t_mid_fmt) // 2))
    time_space_2 = max(1, width - mid_pos - (len(t_mid_fmt) // 2) - len(t_end_fmt))
    time_labels = f"[dim cyan]{t_start_fmt}[/dim cyan]{' ' * time_space_1}[dim white]{t_mid_fmt}[/dim white]{' ' * time_space_2}[dim cyan]{t_end_fmt}[/dim cyan]"

    # Assemble full visual display
    lines = [
        "[bold #94a3b8]Pointers:[/bold #94a3b8] " + "".join(pointer_line),
        *waveform_rows,
        ruler_str,
        time_labels,
    ]

    return "\n".join(lines)
