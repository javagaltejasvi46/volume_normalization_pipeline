"""Media stream and container inspection using ffprobe."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from batch_audio_leveler.models import AudioStreamInfo, ProbeResult


class ProbeError(Exception):
    """Raised when probing a media file fails."""
    pass


def probe_file(file_path: Path, ffprobe_path: Path, timeout_seconds: int = 30) -> ProbeResult:
    """Inspect media file streams, duration, and metadata using ffprobe."""
    if not file_path.is_file():
        raise ProbeError(f"File does not exist: {file_path}")

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
            shell=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as e:
        raise ProbeError(f"Probe timed out after {timeout_seconds} seconds on '{file_path}'.") from e
    except subprocess.CalledProcessError as e:
        raise ProbeError(f"ffprobe failed for '{file_path}': {e.stderr or e.stdout or 'Unknown error'}") from e
    except Exception as e:
        raise ProbeError(f"Failed to probe '{file_path}': {e}") from e

    try:
        data: Dict[str, Any] = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ProbeError(f"ffprobe returned invalid JSON for '{file_path}': {e}") from e

    streams: List[Dict[str, Any]] = data.get("streams", [])
    format_info: Dict[str, Any] = data.get("format", {})

    video_streams: List[Dict[str, Any]] = []
    audio_streams: List[AudioStreamInfo] = []
    has_subtitles = False

    for s in streams:
        c_type = s.get("codec_type")
        if c_type == "video":
            video_streams.append(s)
        elif c_type == "audio":
            idx = int(s.get("index", len(audio_streams)))
            codec_name = s.get("codec_name", "unknown")
            channels = int(s.get("channels", 2))
            sample_rate = int(s.get("sample_rate", 44100))
            bit_rate_raw = s.get("bit_rate")
            bit_rate = int(bit_rate_raw) if bit_rate_raw and bit_rate_raw.isdigit() else None
            tags = s.get("tags", {})
            title = tags.get("title")
            language = tags.get("language")

            audio_streams.append(
                AudioStreamInfo(
                    index=idx,
                    codec_name=codec_name,
                    channels=channels,
                    sample_rate=sample_rate,
                    bit_rate=bit_rate,
                    title=title,
                    language=language,
                )
            )
        elif c_type == "subtitle":
            has_subtitles = True

    duration_seconds: Optional[float] = None
    if "duration" in format_info:
        try:
            duration_seconds = float(format_info["duration"])
        except (ValueError, TypeError):
            pass

    if duration_seconds is None:
        for s in streams:
            if "duration" in s:
                try:
                    duration_seconds = float(s["duration"])
                    break
                except (ValueError, TypeError):
                    pass

    return ProbeResult(
        path=file_path,
        duration_seconds=duration_seconds,
        video_streams=video_streams,
        audio_streams=audio_streams,
        format_name=format_info.get("format_name", "unknown"),
        has_subtitles=has_subtitles,
        raw_probe_json=data,
    )
