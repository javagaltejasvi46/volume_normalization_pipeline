"""FFmpeg execution engine for trimming and segmenting audio files."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable, Optional

from batch_audio_leveler.trimmer.models import TrimJobConfig, TrimResult
from batch_audio_leveler.trimmer.parser import (
    format_timestamp,
    sanitize_filename_part,
)
from batch_audio_leveler.utils.paths import clean_path, ensure_directory, get_unique_output_path


def probe_audio_duration(file_path: Path, ffprobe_path: Path) -> Optional[float]:
    """Inspect file with ffprobe to determine duration and verify audio stream exists."""
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
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=30,
        )
        data = json.loads(proc.stdout)
        # Check that there is at least one audio stream
        audio_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
        if not audio_streams:
            return None
        dur_str = data.get("format", {}).get("duration")
        if dur_str:
            return float(dur_str)
        for s in audio_streams:
            if "duration" in s:
                return float(s["duration"])
    except Exception:
        pass
    return None


def trim_audio_segments(
    config: TrimJobConfig,
    ffmpeg_path: Path,
    ffprobe_path: Optional[Path] = None,
    log_callback: Optional[Callable[[str, str], None]] = None,
) -> TrimResult:
    """Trim one or more audio segments from source_file and export to output_dir."""
    source_file = clean_path(config.source_file)
    output_dir = ensure_directory(config.output_dir)

    if not source_file.is_file():
        raise ValueError(f"Source audio file not found: {source_file}")

    if not config.segments:
        raise ValueError("No trim segments defined to export.")

    # Probe duration if ffprobe is configured
    total_duration: Optional[float] = None
    if ffprobe_path and ffprobe_path.is_file():
        total_duration = probe_audio_duration(source_file, ffprobe_path)

    # Validate all segments for negative pointers, invalid ranges, and collisions
    from batch_audio_leveler.trimmer.collisions import validate_segments_for_export
    val_errors = validate_segments_for_export(config.segments, total_duration)
    if val_errors:
        raise ValueError("Cannot export clips due to segment errors:\n" + "\n".join(val_errors))

    result = TrimResult(source_file=source_file)
    total_segs = len(config.segments)

    for idx, seg in enumerate(config.segments, start=1):
        if seg.start_seconds < 0:
            err = f"Segment {idx} start time cannot be negative: {seg.start_seconds}"
            result.failed_segments.append(err)
            if log_callback:
                log_callback(err, "error")
            continue

        if seg.end_seconds <= seg.start_seconds:
            err = f"Segment {idx} end time ({seg.end_seconds}s) must be greater than start time ({seg.start_seconds}s)"
            result.failed_segments.append(err)
            if log_callback:
                log_callback(err, "error")
            continue

        start_fmt = format_timestamp(seg.start_seconds)
        end_fmt = format_timestamp(seg.end_seconds)

        # Build output filename
        if seg.label and seg.label.strip():
            label_clean = sanitize_filename_part(seg.label.strip())
            file_stem = f"{source_file.stem}_{label_clean}"
        else:
            s_clean = sanitize_filename_part(start_fmt)
            e_clean = sanitize_filename_part(end_fmt)
            file_stem = f"{source_file.stem}_clip_{s_clean}_to_{e_clean}"

        # Determine extension
        if config.output_format.lower() == "mp3":
            ext = ".mp3"
        else:
            orig_suffix = source_file.suffix.lower()
            if orig_suffix in {".mp4", ".m4v"}:
                ext = ".m4a"
            elif orig_suffix:
                ext = orig_suffix
            else:
                ext = ".mp3"

        out_path = get_unique_output_path(output_dir, Path(file_stem + ext))

        if log_callback:
            log_callback(
                f"Slicing clip [{idx}/{total_segs}]: {start_fmt} -> {end_fmt} ({seg.duration_seconds:.1f}s) -> {out_path.name}",
                "info",
            )

        # Build FFmpeg command
        cmd = [
            str(ffmpeg_path),
            "-hide_banner",
            "-nostats",
            "-y",
            "-ss",
            f"{seg.start_seconds:.3f}",
            "-to",
            f"{seg.end_seconds:.3f}",
            "-i",
            str(source_file),
            "-vn",
        ]

        if config.output_format.lower() == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", config.audio_bitrate])
        else:
            cmd.extend(["-c:a", "copy"])

        cmd.append(str(out_path))

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=180,
            )

            # If stream copy failed, try fallback re-encoding
            if (proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0) and config.output_format.lower() != "mp3":
                if log_callback:
                    log_callback(f"Stream copy failed for clip {idx}, retrying with standard audio encoding...", "warning")
                cmd_fallback = [
                    str(ffmpeg_path),
                    "-hide_banner",
                    "-nostats",
                    "-y",
                    "-ss",
                    f"{seg.start_seconds:.3f}",
                    "-to",
                    f"{seg.end_seconds:.3f}",
                    "-i",
                    str(source_file),
                    "-vn",
                    "-c:a",
                    "libmp3lame" if ext == ".mp3" else "aac",
                    "-b:a",
                    config.audio_bitrate,
                    str(out_path),
                ]
                proc = subprocess.run(
                    cmd_fallback,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                    timeout=180,
                )

            if proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
                err_text = proc.stderr.strip() or "FFmpeg exited with error"
                raise RuntimeError(err_text)

            result.exported_files.append(out_path)
            if log_callback:
                log_callback(f"Successfully saved clip: '{out_path.name}'", "success")

        except Exception as e:
            if out_path.exists():
                try:
                    out_path.unlink()
                except Exception:
                    pass
            msg = f"Failed trimming clip {idx} ({start_fmt} - {end_fmt}): {e}"
            result.failed_segments.append(msg)
            if log_callback:
                log_callback(msg, "error")

    return result
