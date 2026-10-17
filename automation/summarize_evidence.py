#!/usr/bin/env python3
"""Build one comparison CSV from evidence_runner summary files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def change_percent(before: float | None, after: float | None) -> str:
    if before is None or after is None or before == 0:
        return ""
    return f"{((before - after) / before) * 100:.3f}"


def summarize(evidence: Path, output: Path, profile: str = 'auto') -> list[dict]:
    candidates = list(evidence.rglob('Q*_summary.json'))
    if profile == 'auto':
        profile = 'micro' if any(path.parent.name == 'micro' for path in candidates) else 'legacy'
    paths = [
        path for path in candidates
        if (path.parent.name == profile if profile != 'legacy' else len(path.relative_to(evidence).parts) <= 2)
    ]
    if not paths:
        raise ValueError(f'No hay resúmenes para el perfil {profile} en {evidence}')
    summaries = [dict(json.loads(path.read_text(encoding='utf-8')), source=str(path.relative_to(evidence))) for path in paths]
    summaries.sort(key=lambda item: (int(item["case"][1:]), item["stage"]))
    by_case = {}
    for item in summaries:
        if item['stage'] in by_case.get(item['case'], {}):
            raise ValueError(f"Resúmenes duplicados para {item['case']} {item['stage']} ({profile})")
        by_case.setdefault(item["case"], {})[item["stage"]] = item

    fields = [
        "case", "stage", "iterations", "rows_returned", "sha256", "min_ms", "mean_ms",
        "median_ms", "p95_ms_nearest_rank", "max_ms", "population_stdev_ms",
        "same_result_as_A", "median_improvement_A_to_stage_percent", "profile", "source",
        "cpu_seconds", "cpu_seconds_per_query", "rss_before_kib", "rss_after_kib",
        "disk_read_bytes", "disk_write_bytes", "batch_seconds", "queries_per_second", "short_batch",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in summaries:
            baseline = by_case[item["case"]].get("A")
            row = {field: item.get(field, "") for field in fields}
            row["same_result_as_A"] = (
                "" if baseline is None else str(item["sha256"] == baseline["sha256"]).lower()
            )
            row["median_improvement_A_to_stage_percent"] = change_percent(
                baseline.get("median_ms") if baseline else None, item.get("median_ms")
            )
            row['profile'] = profile
            os_path = evidence / item['source'].replace('_summary.json', '_os_metadata.json')
            if os_path.exists():
                metrics = json.loads(os_path.read_text(encoding='utf-8'))
                cpu = metrics.get('cpu_seconds')
                duration = metrics.get('batch_elapsed_seconds')
                io = metrics.get('disk_io_delta_bytes') or {}
                row.update(
                    cpu_seconds=cpu,
                    cpu_seconds_per_query=cpu / item['iterations'] if cpu is not None else '',
                    rss_before_kib=metrics['before']['rss_kib'],
                    rss_after_kib=metrics['after']['rss_kib'],
                    disk_read_bytes=io.get('read_bytes', ''),
                    disk_write_bytes=io.get('write_bytes', ''),
                    batch_seconds=duration,
                    queries_per_second=item['iterations'] / duration if duration else '',
                    short_batch=metrics.get('short_batch'),
                )
            writer.writerow(row)
    print(f"Comparison written to {output.resolve()}")
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=Path("evidencias"))
    parser.add_argument("--output", type=Path, default=Path("resultados_comparativos.csv"))
    parser.add_argument('--profile', choices=('auto', 'micro', 'carga', 'legacy'), default='auto')
    args = parser.parse_args()
    summarize(args.evidence, args.output, args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
