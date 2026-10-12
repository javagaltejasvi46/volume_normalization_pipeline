"""CSV report generation for normalization results."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from batch_audio_leveler.models import JobResult


def export_csv_report(results: List[JobResult], report_path: Path) -> Path:
    """Write batch processing results to a CSV file."""
    report_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "source_path",
        "output_path",
        "status",
        "before_i_lufs",
        "before_tp_dbtp",
        "before_lra_lu",
        "target_i_lufs",
        "target_tp_dbtp",
        "requested_gain_db",
        "effective_gain_db",
        "planned_mode",
        "after_i_lufs",
        "after_tp_dbtp",
        "after_lra_lu",
        "processing_seconds",
        "warnings",
        "error_message",
    ]

    with open(report_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for res in results:
            before_m = res.before_measurement
            after_m = res.after_measurement
            plan = res.plan

            row = {
                "source_path": str(res.source_path),
                "output_path": str(res.output_path) if res.output_path else "",
                "status": res.status.value,
                "before_i_lufs": f"{before_m.integrated_lufs:.2f}" if (before_m and before_m.integrated_lufs is not None) else "",
                "before_tp_dbtp": f"{before_m.true_peak_dbtp:.2f}" if (before_m and before_m.true_peak_dbtp is not None) else "",
                "before_lra_lu": f"{before_m.loudness_range_lu:.2f}" if (before_m and before_m.loudness_range_lu is not None) else "",
                "target_i_lufs": f"{plan.batch_target_lufs:.2f}" if plan else "",
                "target_tp_dbtp": f"{plan.true_peak_ceiling_dbtp:.2f}" if plan else "",
                "requested_gain_db": f"{plan.requested_gain_db:+.2f}" if plan else "",
                "effective_gain_db": f"{plan.effective_gain_db:+.2f}" if (plan and plan.effective_gain_db is not None) else "",
                "planned_mode": plan.planned_mode if plan else "",
                "after_i_lufs": f"{after_m.integrated_lufs:.2f}" if (after_m and after_m.integrated_lufs is not None) else "",
                "after_tp_dbtp": f"{after_m.true_peak_dbtp:.2f}" if (after_m and after_m.true_peak_dbtp is not None) else "",
                "after_lra_lu": f"{after_m.loudness_range_lu:.2f}" if (after_m and after_m.loudness_range_lu is not None) else "",
                "processing_seconds": f"{res.processing_seconds:.2f}" if res.processing_seconds is not None else "",
                "warnings": "; ".join(res.warnings),
                "error_message": res.error_message or "",
            }
            writer.writerow(row)

    return report_path
