"""Media metadata extraction to CSV and application from CSV using ffprobe and ffmpeg."""

from __future__ import annotations

import csv
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from batch_audio_leveler.utils.paths import clean_path, ensure_directory

SUPPORTED_MEDIA_EXTENSIONS: Set[str] = {
    ".mp4",
    ".m4v",
    ".m4a",
    ".mp3",
    ".mkv",
    ".mov",
    ".flac",
    ".wav",
    ".aac",
    ".ogg",
}

STANDARD_TAGS = [
    "filename",
    "title",
    "artist",
    "album",
    "genre",
    "year",
    "track",
    "comment",
]


@dataclass
class MetadataApplyResult:
    total_in_csv: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    errors: List[str] = field(default_factory=list)


def get_tag_value(tags: Dict[str, Any], *candidate_keys: str) -> str:
    """Case-insensitive tag retrieval from ffprobe tags dictionary."""
    lower_map = {str(k).lower(): str(v) for k, v in tags.items() if v is not None}
    for cand in candidate_keys:
        val = lower_map.get(cand.lower())
        if val is not None and val.strip():
            return val.strip()
    return ""


def extract_file_tags(
    file_path: Path, ffprobe_path: Path, timeout_seconds: int = 30
) -> Dict[str, str]:
    """Inspect media file format and audio streams to extract standard tags."""
    cmd = [
        str(ffprobe_path),
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        shell=False,
        timeout=timeout_seconds,
    )

    data = json.loads(proc.stdout)
    format_tags: Dict[str, Any] = data.get("format", {}).get("tags", {}) or {}

    # Stream-level fallback tags if format-level tags are missing
    stream_tags: Dict[str, Any] = {}
    for s in data.get("streams", []):
        if s.get("codec_type") == "audio" and "tags" in s:
            stream_tags.update(s.get("tags") or {})

    merged_tags = {**stream_tags, **format_tags}

    return {
        "title": get_tag_value(merged_tags, "title"),
        "artist": get_tag_value(
            merged_tags, "artist", "album_artist", "composer", "author"
        ),
        "album": get_tag_value(merged_tags, "album"),
        "genre": get_tag_value(merged_tags, "genre"),
        "year": get_tag_value(merged_tags, "year", "date", "creation_time"),
        "track": get_tag_value(merged_tags, "track"),
        "comment": get_tag_value(merged_tags, "comment", "description"),
    }


def extract_directory_metadata(
    source_dir: Path,
    output_csv_path: Path,
    ffprobe_path: Path,
    recursive: bool = True,
    log_callback: Optional[Callable[[str, str], None]] = None,
) -> int:
    """Extract standard metadata from all media files in source_dir and export to CSV."""
    source_dir = clean_path(source_dir)
    output_csv_path = clean_path(output_csv_path)

    if not source_dir.is_dir():
        raise ValueError(f"Source directory does not exist: {source_dir}")

    ensure_directory(output_csv_path.parent)

    pattern = source_dir.rglob("*") if recursive else source_dir.glob("*")
    media_files: List[Path] = [
        p
        for p in sorted(pattern)
        if p.is_file() and p.suffix.lower() in SUPPORTED_MEDIA_EXTENSIONS
    ]

    if not media_files:
        raise ValueError(f"No supported media files found in: {source_dir}")

    rows: List[Dict[str, str]] = []
    total = len(media_files)

    for idx, file_path in enumerate(media_files, start=1):
        if log_callback:
            log_callback(f"Extracting [{idx}/{total}]: {file_path.name}", "info")

        try:
            rel_name = file_path.relative_to(source_dir).as_posix()
        except ValueError:
            rel_name = file_path.name

        try:
            tags = extract_file_tags(file_path, ffprobe_path)
        except Exception as e:
            if log_callback:
                log_callback(
                    f"Failed extracting tags for '{file_path.name}': {e}", "warning"
                )
            tags = {
                "title": "",
                "artist": "",
                "album": "",
                "genre": "",
                "year": "",
                "track": "",
                "comment": "",
            }

        rows.append(
            {
                "filename": rel_name,
                **tags,
            }
        )

    # Write CSV with utf-8-sig encoding for seamless Excel/Windows Unicode support
    with open(output_csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=STANDARD_TAGS)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def apply_metadata_from_csv(
    csv_path: Path,
    source_dir: Path,
    output_dir: Path,
    ffmpeg_path: Path,
    log_callback: Optional[Callable[[str, str], None]] = None,
) -> MetadataApplyResult:
    """Update metadata of media files in source_dir using values from CSV and save to output_dir."""
    csv_path = clean_path(csv_path)
    source_dir = clean_path(source_dir)
    output_dir = ensure_directory(output_dir)

    if not csv_path.is_file():
        raise ValueError(f"CSV file does not exist: {csv_path}")
    if not source_dir.is_dir():
        raise ValueError(f"Source directory does not exist: {source_dir}")

    # Read CSV rows
    content_rows: List[Dict[str, str]] = []
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(csv_path, mode="r", newline="", encoding=enc) as f:
                reader = csv.DictReader(f)
                content_rows = [r for r in reader if r]
            break
        except UnicodeDecodeError:
            continue

    if not content_rows:
        raise ValueError(f"No data rows found in CSV: {csv_path}")

    # Build quick lookup indices for source files
    all_source_files = [p for p in source_dir.rglob("*") if p.is_file()]
    rel_map: Dict[str, Path] = {}
    basename_map: Dict[str, Path] = {}
    for p in all_source_files:
        try:
            rel = p.relative_to(source_dir).as_posix().lower()
            rel_map[rel] = p
        except ValueError:
            pass
        basename_map[p.name.lower()] = p

    result = MetadataApplyResult(total_in_csv=len(content_rows))

    for idx, row in enumerate(content_rows, start=1):
        filename_raw = (row.get("filename") or "").strip()
        if not filename_raw:
            result.skipped_count += 1
            continue

        # Match corresponding source file
        matched_path: Optional[Path] = None
        direct = source_dir / filename_raw
        if direct.is_file():
            matched_path = direct
        elif filename_raw.replace("\\", "/").lower() in rel_map:
            matched_path = rel_map[filename_raw.replace("\\", "/").lower()]
        elif Path(filename_raw).name.lower() in basename_map:
            matched_path = basename_map[Path(filename_raw).name.lower()]

        if not matched_path:
            msg = f"Source file not found for row {idx}: '{filename_raw}'"
            result.skipped_count += 1
            result.errors.append(msg)
            if log_callback:
                log_callback(msg, "warning")
            continue

        # Target output destination preserves relative folder hierarchy
        try:
            rel_subpath = matched_path.relative_to(source_dir)
        except ValueError:
            rel_subpath = Path(matched_path.name)

        target_output = output_dir / rel_subpath
        target_output.parent.mkdir(parents=True, exist_ok=True)

        if log_callback:
            log_callback(
                f"Updating [{idx}/{result.total_in_csv}]: {matched_path.name} -> {target_output.name}",
                "info",
            )

        temp_output = target_output.with_name(
            f"{target_output.stem}_tmp_{int(time.time() * 1000)}{target_output.suffix}"
        )

        # Build FFmpeg command with stream copy (lossless, 0 re-encoding)
        cmd = [
            str(ffmpeg_path),
            "-hide_banner",
            "-nostats",
            "-y",
            "-i",
            str(matched_path),
            "-map",
            "0",
            "-c",
            "copy",
        ]

        tag_specs = [
            ("title", row.get("title")),
            ("artist", row.get("artist")),
            ("album", row.get("album")),
            ("genre", row.get("genre")),
            ("date", row.get("year")),
            ("track", row.get("track")),
            ("comment", row.get("comment")),
        ]

        for tag_key, tag_val in tag_specs:
            if tag_val is not None:
                cmd.extend(["-metadata", f"{tag_key}={tag_val.strip()}"])

        cmd.append(str(temp_output))

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                shell=False,
                timeout=180,
            )
            if proc.returncode != 0 or not temp_output.is_file():
                err = proc.stderr.strip() or "FFmpeg exited with error"
                raise RuntimeError(err)

            # Atomic replace
            if target_output.exists():
                target_output.unlink()
            temp_output.replace(target_output)
            result.updated_count += 1
        except Exception as e:
            if temp_output.exists():
                try:
                    temp_output.unlink()
                except Exception:
                    pass
            msg = f"Failed writing metadata for '{matched_path.name}': {e}"
            result.failed_count += 1
            result.errors.append(msg)
            if log_callback:
                log_callback(msg, "error")

    return result
