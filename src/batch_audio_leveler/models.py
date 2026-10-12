"""Data models for batch audio leveler."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class NormalizationMode(str, Enum):
    BATCH_MEDIAN = "batch_median"
    FIXED = "fixed"


class ProcessingStrategy(str, Enum):
    LINEAR = "linear"
    DYNAMIC = "dynamic"


class JobStatus(str, Enum):
    QUEUED = "queued"
    ANALYZED = "analyzed"
    PROCESSING = "processing"
    VERIFIED = "verified"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AudioStreamInfo:
    index: int
    codec_name: str
    channels: int
    sample_rate: int
    bit_rate: Optional[int] = None
    title: Optional[str] = None
    language: Optional[str] = None


@dataclass
class ProbeResult:
    path: Path
    duration_seconds: Optional[float]
    video_streams: List[Dict[str, Any]]
    audio_streams: List[AudioStreamInfo]
    format_name: str
    has_subtitles: bool = False
    raw_probe_json: Optional[Dict[str, Any]] = None


@dataclass
class AudioMeasurement:
    path: Path
    audio_stream_index: int = 0
    integrated_lufs: Optional[float] = None
    true_peak_dbtp: Optional[float] = None
    loudness_range_lu: Optional[float] = None
    threshold_lufs: Optional[float] = None
    target_offset: Optional[float] = None
    measurement_valid: bool = False
    is_silent: bool = False
    raw_ffmpeg_json: Optional[Dict[str, Any]] = None
    measured_at: Optional[str] = None


@dataclass
class NormalizationPlan:
    path: Path
    batch_target_lufs: float
    requested_gain_db: float
    planned_mode: str  # 'linear' or 'dynamic'
    true_peak_ceiling_dbtp: float
    estimated_output_peak_dbtp: Optional[float] = None
    peak_constraint_applied: bool = False
    expected_target_reachable: bool = True
    effective_gain_db: Optional[float] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class JobResult:
    source_path: Path
    output_path: Optional[Path] = None
    status: JobStatus = JobStatus.QUEUED
    before_measurement: Optional[AudioMeasurement] = None
    after_measurement: Optional[AudioMeasurement] = None
    plan: Optional[NormalizationPlan] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    processing_seconds: Optional[float] = None


@dataclass
class FileJob:
    path: Path
    selected_stream_index: int = 0
    probe_result: Optional[ProbeResult] = None
    measurement: Optional[AudioMeasurement] = None
    plan: Optional[NormalizationPlan] = None
    result: Optional[JobResult] = None
