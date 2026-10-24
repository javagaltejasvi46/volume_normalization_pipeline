"""Flexible timestamp parsing and formatting utilities."""

from __future__ import annotations

import re
from typing import Union


def parse_timestamp(val: Union[str, float, int]) -> float:
    """Parse flexible timestamp expressions into total seconds.

    Supported formats:
      - Raw seconds: '90', '90.5', '90s', 90, 90.5
      - MM:SS: '01:30', '1:30', '00:45.5'
      - HH:MM:SS: '01:30:00', '00:01:30'
      - Descriptive: '1m 30s', '1h 15m', '45s'
    """
    if isinstance(val, (int, float)):
        if val < 0:
            raise ValueError(f"Timestamp cannot be negative: {val}")
        return float(val)

    s = str(val).strip().lower()
    if not s:
        raise ValueError("Timestamp cannot be empty.")

    # Remove trailing 's' if e.g. "90s" or "1.5s"
    if s.endswith("s") and not (":" in s or "m" in s or "h" in s):
        s = s[:-1].strip()

    # Direct float/int check
    try:
        f = float(s)
        if f < 0:
            raise ValueError(f"Timestamp cannot be negative: {val}")
        return f
    except ValueError:
        pass

    # Check for formats with h/m/s e.g. "1h 30m 15s" or "1m30s"
    hms_match = re.fullmatch(
        r"(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+(?:\.\d+)?)\s*m)?\s*(?:(\d+(?:\.\d+)?)\s*s)?",
        s,
    )
    if hms_match and any(hms_match.groups()):
        h_str, m_str, s_str = hms_match.groups()
        total = 0.0
        if h_str:
            total += float(h_str) * 3600
        if m_str:
            total += float(m_str) * 60
        if s_str:
            total += float(s_str)
        return total

    # Check for colon notation: HH:MM:SS or MM:SS
    parts = s.split(":")
    if len(parts) == 2:
        try:
            m = float(parts[0])
            sec = float(parts[1])
            if m < 0 or sec < 0:
                raise ValueError(f"Negative values not allowed in timestamp: {val}")
            return m * 60.0 + sec
        except ValueError as e:
            raise ValueError(f"Invalid MM:SS timestamp '{val}': {e}") from e
    elif len(parts) == 3:
        try:
            h = float(parts[0])
            m = float(parts[1])
            sec = float(parts[2])
            if h < 0 or m < 0 or sec < 0:
                raise ValueError(f"Negative values not allowed in timestamp: {val}")
            return h * 3600.0 + m * 60.0 + sec
        except ValueError as e:
            raise ValueError(f"Invalid HH:MM:SS timestamp '{val}': {e}") from e

    raise ValueError(
        f"Invalid timestamp format: '{val}'. Expected 'HH:MM:SS', 'MM:SS', or seconds (e.g. '01:30' or '90s')."
    )


def format_timestamp(seconds: float, include_ms: bool = False) -> str:
    """Format total seconds into human-readable MM:SS or HH:MM:SS."""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if include_ms:
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:06.3f}"
        return f"{m:02d}:{s:06.3f}"
    else:
        sec_int = int(s)
        if h > 0:
            return f"{h:02d}:{m:02d}:{sec_int:02d}"
        return f"{m:02d}:{sec_int:02d}"


def sanitize_filename_part(text: str) -> str:
    """Replace illegal characters for filenames with dashes or underscores."""
    cleaned = re.sub(r'[:/\\?*"<>|]', "-", text)
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned.strip("._-")
