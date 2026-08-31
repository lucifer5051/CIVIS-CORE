import json
import os
from typing import Any, Dict

from civis.observability.models import OperationalReport


class OperationalReportExporter:
    """
    Serializes and exports comprehensive operational health & performance reports.
    """

    @classmethod
    def to_dict(cls, report: OperationalReport) -> Dict[str, Any]:
        return {
            "report_id": report.report_id,
            "generated_at": round(report.generated_at, 4),
            "system_status": report.system_status.value,
            "runtime_summary": report.runtime_summary,
            "throughput_metrics": report.throughput_metrics,
            "latency_percentiles": {
                stg: {
                    "count": summ.count,
                    "min_ms": summ.min_ms,
                    "max_ms": summ.max_ms,
                    "mean_ms": summ.mean_ms,
                    "p50_ms": summ.p50_ms,
                    "p95_ms": summ.p95_ms,
                    "p99_ms": summ.p99_ms,
                }
                for stg, summ in report.latency_percentiles.items()
            },
            "queue_statistics": report.queue_statistics,
            "active_errors": [err.to_dict() for err in report.active_errors],
            "diagnostic_findings": [f.to_dict() for f in report.diagnostic_findings],
            "alert_statistics": report.alert_statistics,
        }

    @classmethod
    def to_json(cls, report: OperationalReport, indent: int = 2) -> str:
        return json.dumps(cls.to_dict(report), indent=indent, default=str)

    @classmethod
    def export_file(cls, report: OperationalReport, file_path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(cls.to_json(report))
