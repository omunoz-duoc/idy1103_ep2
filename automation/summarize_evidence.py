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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=Path("evidencias"))
    parser.add_argument("--output", type=Path, default=Path("resultados_comparativos.csv"))
    args = parser.parse_args()
    summaries = [json.loads(path.read_text(encoding="utf-8")) for path in args.evidence.glob("Q*_summary.json")]
    summaries.sort(key=lambda item: (int(item["case"][1:]), item["stage"]))
    by_case = {}
    for item in summaries:
        by_case.setdefault(item["case"], {})[item["stage"]] = item

    fields = [
        "case", "stage", "iterations", "rows_returned", "sha256", "min_ms", "mean_ms",
        "median_ms", "p95_ms_nearest_rank", "max_ms", "population_stdev_ms",
        "same_result_as_A", "median_improvement_A_to_stage_percent",
    ]
    with args.output.open("w", encoding="utf-8", newline="") as handle:
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
            writer.writerow(row)
    print(f"Comparison written to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
