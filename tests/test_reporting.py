from pathlib import Path
import json
import csv

from batch_audio_leveler.models import (
    AudioMeasurement,
    JobResult,
    JobStatus,
    NormalizationPlan,
)
from batch_audio_leveler.reporting.csv_report import export_csv_report
from batch_audio_leveler.reporting.json_report import export_json_report


def test_export_reports(tmp_path: Path):
    src = tmp_path / "clip.mp4"
    out = tmp_path / "out_clip.mp4"

    m_before = AudioMeasurement(
        path=src,
        integrated_lufs=-22.5,
        true_peak_dbtp=-4.1,
        loudness_range_lu=7.2,
        measurement_valid=True,
    )
    m_after = AudioMeasurement(
        path=out,
        integrated_lufs=-16.1,
        true_peak_dbtp=-2.0,
        loudness_range_lu=7.0,
        measurement_valid=True,
    )
    plan = NormalizationPlan(
        path=src,
        batch_target_lufs=-16.0,
        requested_gain_db=6.5,
        planned_mode="linear",
        true_peak_ceiling_dbtp=-2.0,
        effective_gain_db=6.5,
    )
    res = JobResult(
        source_path=src,
        output_path=out,
        status=JobStatus.VERIFIED,
        before_measurement=m_before,
        after_measurement=m_after,
        plan=plan,
        warnings=["Test note"],
        processing_seconds=1.25,
    )

    csv_path = tmp_path / "report.csv"
    export_csv_report([res], csv_path)
    assert csv_path.exists()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 1
        assert reader[0]["source_path"] == str(src)
        assert reader[0]["status"] == "verified"
        assert reader[0]["before_i_lufs"] == "-22.50"
        assert reader[0]["after_i_lufs"] == "-16.10"

    json_path = tmp_path / "report.json"
    export_json_report([res], json_path)
    assert json_path.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["total_jobs"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["status"] == "verified"
        assert data["results"][0]["before_measurement"]["integrated_lufs"] == -22.5
