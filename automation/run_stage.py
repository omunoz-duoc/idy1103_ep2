#!/usr/bin/env python3
"""Run all requested EP2 cases for safe stages A or B."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect A or B evidence for several cases.")
    parser.add_argument("--stage", required=True, choices=("A", "B"), type=str.upper)
    parser.add_argument("--cases", nargs="+", default=["Q1", "Q2", "Q3", "Q4", "Q5"])
    parser.add_argument("--params", type=Path, default=Path("sql/00_parametros.sql"))
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=2)
    args = parser.parse_args()

    runner = Path(__file__).with_name("evidence_runner.py")
    for case in (case.upper() for case in args.cases):
        query = Path("queries") / f"{case}_{args.stage}.sql"
        command = [
            sys.executable,
            str(runner),
            "--case", case,
            "--stage", args.stage,
            "--query", str(query),
            "--params", str(args.params),
            "--iterations", str(args.iterations),
            "--warmups", str(args.warmups),
        ]
        print(f"\n=== Collecting {case} stage {args.stage} ===", flush=True)
        subprocess.run(command, check=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Stopped because one evidence run failed (exit {exc.returncode}).", file=sys.stderr)
        raise SystemExit(exc.returncode)
