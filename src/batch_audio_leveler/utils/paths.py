"""Path resolution and validation utilities."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Union


def clean_path(raw: Union[str, Path]) -> Path:
    """Normalize input path string, stripping quotes and resolving cleanly."""
    if isinstance(raw, Path):
        text = str(raw)
    else:
        text = str(raw)
    text = text.strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    # Expand user ~ if present
    path = Path(os.path.expanduser(text)).resolve()
    return path


def is_mp4_file(path: Path) -> bool:
    """Check if file has an MP4 extension (case-insensitive)."""
    return path.is_file() and path.suffix.lower() in {".mp4", ".m4v"}


def ensure_directory(dir_path: Path) -> Path:
    """Ensure directory exists and is writable."""
    dir_path = clean_path(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)
    # Test writability by checking directory permissions
    test_file = dir_path / f".write_test_{int(time.time() * 1000)}"
    try:
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        raise PermissionError(f"Output directory '{dir_path}' is not writable: {e}") from e
    return dir_path


def get_unique_output_path(output_dir: Path, source_path: Path, overwrite: bool = False) -> Path:
    """Return destination path in output_dir for source_path.

    If overwrite is False and file exists, adds an incrementing suffix.
    """
    output_dir = ensure_directory(output_dir)
    target = output_dir / source_path.name
    if overwrite or not target.exists():
        return target

    # Suffix logic
    stem = source_path.stem
    ext = source_path.suffix
    counter = 1
    while True:
        candidate = output_dir / f"{stem}_{counter}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def get_temp_output_path(final_path: Path) -> Path:
    """Return a temporary output path in the same folder as final_path."""
    parent = final_path.parent
    timestamp = int(time.time() * 1000)
    return parent / f".tmp_{final_path.stem}_{timestamp}{final_path.suffix}"


def format_path_for_display(path: Path, max_length: int = 45) -> str:
    """Truncate path cleanly for terminal display."""
    p_str = str(path)
    if len(p_str) <= max_length:
        return p_str
    half = (max_length - 3) // 2
    return p_str[:half] + "..." + p_str[-half:]
