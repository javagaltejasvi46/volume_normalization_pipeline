"""JSON report generation for normalization results."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from batch_audio_leveler.models import JobResult


def _serialize_obj(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "value"):
        return obj.value
    if hasattr(obj, "__dict__"):
        return asdict(obj)
    return str(obj)


def export_json_report(results: List[JobResult], report_path: Path) -> Path:
    """Write batch processing results to a JSON file."""
    report_path.parent.mkdir(parents=True, exist_ok=True)

    items: List[Dict[str, Any]] = []
    for res in results:
        before_m = res.before_measurement
        after_m = res.after_measurement
        plan = res.plan

        item = {
            "source_path": str(res.source_path),
            "output_path": str(res.output_path) if res.output_path else None,
            "status": res.status.value,
            "started_at": res.started_at,
            "finished_at": res.finished_at,
            "processing_seconds": res.processing_seconds,
            "error_message": res.error_message,
            "warnings": res.warnings,
            "plan": {
                "batch_target_lufs": plan.batch_target_lufs,
                "requested_gain_db": plan.requested_gain_db,
                "effective_gain_db": plan.effective_gain_db,
                "planned_mode": plan.planned_mode,
                "true_peak_ceiling_dbtp": plan.true_peak_ceiling_dbtp,
                "peak_constraint_applied": plan.peak_constraint_applied,
                "expected_target_reachable": plan.expected_target_reachable,
            } if plan else None,
            "before_measurement": {
                "integrated_lufs": before_m.integrated_lufs,
                "true_peak_dbtp": before_m.true_peak_dbtp,
                "loudness_range_lu": before_m.loudness_range_lu,
                "threshold_lufs": before_m.threshold_lufs,
                "target_offset": before_m.target_offset,
                "measurement_valid": before_m.measurement_valid,
                "is_silent": before_m.is_silent,
            } if before_m else None,
            "after_measurement": {
                "integrated_lufs": after_m.integrated_lufs,
                "true_peak_dbtp": after_m.true_peak_dbtp,
                "loudness_range_lu": after_m.loudness_range_lu,
                "threshold_lufs": after_m.threshold_lufs,
                "target_offset": after_m.target_offset,
                "measurement_valid": after_m.measurement_valid,
                "is_silent": after_m.is_silent,
            } if after_m else None,
        }
        items.append(item)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_jobs": len(results),
        "results": items,
    }

    with open(report_path, mode="w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return report_path
