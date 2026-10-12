"""Discovery and validation of FFmpeg and FFprobe binaries."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ToolInfo:
    path: Path
    version: str
    available: bool
    error_message: Optional[str] = None


@dataclass
class FFmpegEnvironment:
    ffmpeg: ToolInfo
    ffprobe: ToolInfo
    has_loudnorm: bool

    @property
    def is_ready(self) -> bool:
        return self.ffmpeg.available and self.ffprobe.available and self.has_loudnorm


def find_tool(name: str, custom_path: Optional[Path] = None) -> ToolInfo:
    """Find and validate a tool (ffmpeg or ffprobe)."""
    target_path: Optional[Path] = None

    if custom_path:
        custom_p = Path(custom_path).resolve()
        if custom_p.is_file():
            target_path = custom_p
        else:
            return ToolInfo(
                path=custom_p,
                version="",
                available=False,
                error_message=f"Specified {name} binary was not found at '{custom_p}'.",
            )
    else:
        found = shutil.which(name)
        if found:
            target_path = Path(found).resolve()
        else:
            return ToolInfo(
                path=Path(name),
                version="",
                available=False,
                error_message=(
                    f"'{name}' was not found on system PATH.\n"
                    f"Setup guidance for Windows:\n"
                    f"  1. Install via winget: 'winget install Gyan.FFmpeg'\n"
                    f"  2. Or download from https://www.gyan.dev/ffmpeg/builds/ and add the 'bin' folder to PATH.\n"
                    f"  3. Alternatively, specify the binary path in config."
                ),
            )

    try:
        proc = subprocess.run(
            [str(target_path), "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            shell=False,
            timeout=5,
        )
        first_line = proc.stdout.splitlines()[0] if proc.stdout else ""
        match = re.search(r"version\s+([^\s]+)", first_line)
        version_str = match.group(1) if match else first_line
        return ToolInfo(path=target_path, version=version_str, available=True)
    except Exception as e:
        return ToolInfo(
            path=target_path,
            version="",
            available=False,
            error_message=f"Failed to execute {name} at '{target_path}': {e}",
        )


def check_loudnorm_support(ffmpeg_path: Path) -> bool:
    """Check if loudnorm filter is available in the installed ffmpeg."""
    try:
        proc = subprocess.run(
            [str(ffmpeg_path), "-hide_banner", "-filters"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            shell=False,
            timeout=5,
        )
        return "loudnorm" in proc.stdout
    except Exception:
        return False


def discover_ffmpeg(
    custom_ffmpeg: Optional[Path] = None,
    custom_ffprobe: Optional[Path] = None,
) -> FFmpegEnvironment:
    """Discover FFmpeg and FFprobe binaries and check requirements."""
    ffmpeg_info = find_tool("ffmpeg", custom_ffmpeg)
    ffprobe_info = find_tool("ffprobe", custom_ffprobe)

    has_loudnorm = False
    if ffmpeg_info.available:
        has_loudnorm = check_loudnorm_support(ffmpeg_info.path)
        if not has_loudnorm:
            ffmpeg_info.available = False
            ffmpeg_info.error_message = "The discovered FFmpeg build does not include the 'loudnorm' filter."

    return FFmpegEnvironment(
        ffmpeg=ffmpeg_info,
        ffprobe=ffprobe_info,
        has_loudnorm=has_loudnorm,
    )
