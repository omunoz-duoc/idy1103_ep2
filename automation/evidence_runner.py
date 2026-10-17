#!/usr/bin/env python3
"""Collect reproducible MySQL evidence for one EP2 query and stage."""

from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import decimal
import hashlib
import json
import math
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from os_monitor import ProcessMonitor

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:  # pragma: no cover - exercised by the install check
    mysql = None
    MySQLError = Exception


STATUS_NAMES = (
    "Handler_read_key",
    "Handler_read_next",
    "Handler_read_rnd_next",
    "Created_tmp_tables",
    "Created_tmp_disk_tables",
    "Sort_rows",
    "Sort_merge_passes",
    "Select_scan",
    "Select_full_join",
)

DATASET_TABLES = (
    "ep2_customers",
    "ep2_products",
    "ep2_stores",
    "ep2_orders",
    "ep2_order_items",
    "ep2_payments",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect plans, timings, results, checksums, counters, and indexes."
    )
    parser.add_argument("--case", required=True, dest="case_id", type=str.upper)
    parser.add_argument("--stage", required=True, choices=("A", "B", "C"), type=str.upper)
    parser.add_argument("--query", required=True, type=Path)
    parser.add_argument("--params", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="default: evidencias/Qn")
    parser.add_argument("--host", default=os.getenv("EP2_MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("EP2_MYSQL_PORT", "3306")))
    parser.add_argument("--user", default=os.getenv("EP2_MYSQL_USER", "root"))
    parser.add_argument("--database", default=os.getenv("EP2_MYSQL_DATABASE", "ep2_lab"))
    parser.add_argument(
        "--password-env",
        default="EP2_MYSQL_PASSWORD",
        help="environment variable containing the password (default: EP2_MYSQL_PASSWORD)",
    )
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--connect-timeout", type=int, default=10)
    parser.add_argument("--pidstat-pid", type=int, help="local MySQL PID to sample during the batch")
    parser.add_argument("--pidstat-interval", type=int, default=1)
    parser.add_argument("--pidstat-sudo", action="store_true", help="use cached sudo credentials for OS sampling only")
    parser.add_argument("--extended", action="store_true", help="collect extra plans, global counters, waits and index sizes")
    args = parser.parse_args()
    if not re.fullmatch(r"Q[1-9][0-9]*", args.case_id):
        parser.error("--case must look like Q1, Q2, etc.")
    if args.output is None:
        args.output = Path('evidencias') / args.case_id
    if args.warmups < 0 or args.iterations < 1:
        parser.error("--warmups must be >= 0 and --iterations must be >= 1")
    if args.pidstat_interval < 1 or (args.pidstat_pid is not None and args.pidstat_pid < 1):
        parser.error("--pidstat-pid and --pidstat-interval must be positive")
    return args


def split_sql(text: str) -> list[str]:
    """Split simple SQL scripts while respecting strings and SQL comments."""
    statements: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    line_comment = False
    block_comment = False
    i = 0
    while i < len(text):
        char = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
                buf.append(char)
            i += 1
            continue
        if block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                i += 2
            else:
                i += 1
            continue
        if quote:
            buf.append(char)
            if char == "\\" and i + 1 < len(text):
                buf.append(text[i + 1])
                i += 2
                continue
            if char == quote:
                if nxt == quote and quote in ("'", '"'):
                    buf.append(nxt)
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if char in ("'", '"', "`"):
            quote = char
            buf.append(char)
            i += 1
        elif char == "#" or (char == "-" and nxt == "-" and (i + 2 == len(text) or text[i + 2].isspace())):
            line_comment = True
            i += 1 if char == "#" else 2
        elif char == "/" and nxt == "*":
            block_comment = True
            i += 2
        elif char == ";":
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf.clear()
            i += 1
        else:
            buf.append(char)
            i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    if quote or block_comment:
        raise ValueError("SQL file has an unterminated quote or block comment")
    return statements


def read_query(path: Path) -> str:
    statements = split_sql(path.read_text(encoding="utf-8"))
    if len(statements) != 1:
        raise ValueError(f"{path} must contain exactly one SQL statement")
    query = statements[0].strip()
    if not re.match(r"^(SELECT|WITH)\b", query, flags=re.IGNORECASE):
        raise ValueError("The query file must contain a read-only SELECT/WITH statement")
    return query


def read_params(path: Path) -> list[str]:
    statements = split_sql(path.read_text(encoding="utf-8"))
    invalid = [statement for statement in statements if not re.match(r"^SET\s+@", statement, re.I)]
    if invalid:
        raise ValueError("The parameter file may contain only SET @variable := value statements")
    return statements


def canonical_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, decimal.Decimal):
        return {"type": "decimal", "value": format(value, "f")}
    if isinstance(value, float):
        return {"type": "float", "value": value.hex()}
    if isinstance(value, (dt.datetime, dt.time)):
        return {"type": type(value).__name__, "value": value.isoformat(timespec="microseconds")}
    if isinstance(value, dt.date):
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"type": "bytes", "value": base64.b64encode(bytes(value)).decode("ascii")}
    return {"type": "string", "value": str(value)}


def canonical_row(row: Sequence[Any]) -> str:
    return json.dumps(
        [canonical_value(value) for value in row],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def result_checksum(columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Hash a typed row multiset, so harmless output ordering changes do not fail."""
    digest = hashlib.sha256()
    digest.update(json.dumps(list(columns), ensure_ascii=False, separators=(",", ":")).encode())
    digest.update(b"\n")
    for row in sorted(canonical_row(row) for row in rows):
        digest.update(row.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def csv_value(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat(sep=" ") if isinstance(value, dt.datetime) else value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "base64:" + base64.b64encode(bytes(value)).decode("ascii")
    return str(value)


def execute_fetch(cursor: Any, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
    cursor.execute(sql)
    columns = [item[0] for item in (cursor.description or [])]
    rows = cursor.fetchall() if cursor.description else []
    while cursor.nextset():
        if cursor.description:
            cursor.fetchall()
    return columns, rows


def status_snapshot(cursor: Any) -> dict[str, int]:
    names = ",".join("%s" for _ in STATUS_NAMES)
    cursor.execute(f"SHOW SESSION STATUS WHERE Variable_name IN ({names})", STATUS_NAMES)
    return {str(name): int(value) for name, value in cursor.fetchall()}


def write_status(path: Path, before: dict[str, int], after: dict[str, int]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("metric", "before", "after", "delta"))
        for name in STATUS_NAMES:
            first, last = before.get(name, 0), after.get(name, 0)
            writer.writerow((name, first, last, last - first))


def write_rows(path: Path, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([csv_value(value) for value in row])


def write_plan(cursor: Any, path: Path, prefix: str, query: str) -> None:
    columns, rows = execute_fetch(cursor, f"{prefix} {query}")
    with path.open("w", encoding="utf-8") as handle:
        if len(columns) == 1:
            handle.write("\n".join(str(row[0]) for row in rows))
            handle.write("\n")
        else:
            handle.write("\t".join(columns) + "\n")
            for row in rows:
                handle.write("\t".join(csv_value(value) for value in row) + "\n")


def write_indexes(cursor: Any, path: Path, database: str) -> None:
    cursor.execute(
        """
        SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME,
               COLLATION, CARDINALITY, INDEX_TYPE
        FROM information_schema.statistics
        WHERE table_schema=%s
          AND table_name IN (%s)
        ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
        """ % ("%s", ",".join("%s" for _ in DATASET_TABLES)),
        (database, *DATASET_TABLES),
    )
    columns = [item[0] for item in cursor.description]
    write_rows(path, columns, cursor.fetchall())


def write_table_sizes(cursor: Any, path: Path, database: str) -> None:
    cursor.execute(
        """
        SELECT TABLE_NAME, TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH,
               DATA_FREE, CREATE_TIME, UPDATE_TIME
        FROM information_schema.tables
        WHERE table_schema=%s
          AND table_name IN (%s)
        ORDER BY TABLE_NAME
        """ % ("%s", ",".join("%s" for _ in DATASET_TABLES)),
        (database, *DATASET_TABLES),
    )
    columns = [item[0] for item in cursor.description]
    write_rows(path, columns, cursor.fetchall())


def write_metadata(cursor: Any, path: Path, args: argparse.Namespace) -> None:
    cursor.execute(
        "SELECT VERSION(), @@version_comment, DATABASE(), CONNECTION_ID(), NOW(), @@session.time_zone"
    )
    version, comment, database, connection_id, server_time, timezone = cursor.fetchone()
    content = {
        "collected_at_client": dt.datetime.now().astimezone().isoformat(),
        "mysql_version": version,
        "mysql_distribution": comment,
        "database": database,
        "connection_id": connection_id,
        "server_time": csv_value(server_time),
        "session_time_zone": timezone,
        "host": args.host,
        "port": args.port,
        "case": args.case_id,
        "stage": args.stage,
        "warmups": args.warmups,
        "iterations": args.iterations,
    }
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def try_performance_schema(cursor: Any, path: Path, query: str, tag: str) -> None:
    """Run one separately-labelled diagnostic execution and capture its server event."""
    tagged_query = f"/* {tag} */ {query}"
    try:
        cursor.execute(
            "SELECT THREAD_ID FROM performance_schema.threads WHERE PROCESSLIST_ID=CONNECTION_ID()"
        )
        found = cursor.fetchone()
        if not found:
            raise RuntimeError("No Performance Schema thread was found for this connection")
        thread_id = found[0]
        execute_fetch(cursor, tagged_query)
        failures = []
        for history in ('events_statements_history_long', 'events_statements_history'):
            try:
                cursor.execute(
                    f"""
                    SELECT EVENT_ID, SQL_TEXT, ROUND(TIMER_WAIT/1e9,3) AS elapsed_ms,
                           ROUND(LOCK_TIME/1e9,3) AS lock_ms, ROWS_EXAMINED, ROWS_SENT,
                           CREATED_TMP_TABLES, CREATED_TMP_DISK_TABLES, SORT_ROWS, SELECT_SCAN
                    FROM performance_schema.{history}
                    WHERE THREAD_ID=%s AND SQL_TEXT LIKE %s
                    ORDER BY EVENT_ID DESC LIMIT 1
                    """,
                    (thread_id, f"/* {tag} */%"),
                )
                columns = [item[0] for item in cursor.description]
                rows = cursor.fetchall()
                if not rows:
                    failures.append(f'{history}: tagged event unavailable')
                    continue
                write_rows(path, columns, rows)
                path.with_suffix('.status.json').write_text(
                    json.dumps({'available': True, 'source': history}) + '\n', encoding='utf-8'
                )
                return
            except Exception as exc:
                failures.append(f'{history}: {exc}')
        raise RuntimeError('; '.join(failures))
    except Exception as exc:  # permissions/configuration differ between lab installations
        path.write_text(
            "Performance Schema evidence unavailable. This does not invalidate the timing run.\n"
            f"Reason: {type(exc).__name__}: {exc}\n",
            encoding="utf-8",
        )
        path.with_suffix('.status.json').write_text(
            json.dumps({'available': False, 'reason': str(exc)}) + '\n', encoding='utf-8'
        )


def percentile_nearest_rank(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def main() -> int:
    args = parse_args()
    if mysql is None:
        print(
            "Missing dependency. Run: python3 -m pip install -r automation/requirements.txt",
            file=sys.stderr,
        )
        return 2
    password = os.getenv(args.password_env)
    if password is None:
        print(f"Set {args.password_env} before running; do not put the password in evidence files.", file=sys.stderr)
        return 2

    query = read_query(args.query)
    params = read_params(args.params)
    args.output.mkdir(parents=True, exist_ok=True)
    stem = f"{args.case_id}_{args.stage}"

    connection = mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=password,
        database=args.database,
        autocommit=True,
        connection_timeout=args.connect_timeout,
        charset="utf8mb4",
        use_unicode=True,
    )
    try:
        cursor = connection.cursor()
        for statement in params:
            cursor.execute(statement)

        (args.output / f"{stem}_query.sql").write_text(query + ";\n", encoding="utf-8")
        (args.output / f"{stem}_params.sql").write_text(
            args.params.read_text(encoding="utf-8"), encoding="utf-8"
        )
        write_metadata(cursor, args.output / f"{stem}_metadata.json", args)
        write_indexes(cursor, args.output / f"{stem}_indexes.csv", args.database)
        write_table_sizes(cursor, args.output / f"{stem}_table_sizes.csv", args.database)
        write_plan(cursor, args.output / f"{stem}_tree.txt", "EXPLAIN FORMAT=TREE", query)
        write_plan(cursor, args.output / f"{stem}_analyze.txt", "EXPLAIN ANALYZE", query)
        if args.extended:
            from extra_evidence import extra_plans, snapshot, global_delta, index_sizes
            extra_plans(cursor, args.output, stem, query)
            index_sizes(cursor, args.output, f'{stem}_sizes')

        for _ in range(args.warmups):
            execute_fetch(cursor, query)

        if args.extended:
            snapshot(cursor, args.output, f'{stem}_before')

        timing_rows: list[dict[str, Any]] = []
        reference_columns: list[str] | None = None
        reference_rows: list[tuple[Any, ...]] | None = None
        reference_checksum: str | None = None
        with ProcessMonitor(args.pidstat_pid, args.pidstat_interval, args.output, stem, args.pidstat_sudo):
            before = status_snapshot(cursor)
            for iteration in range(1, args.iterations + 1):
                started = time.perf_counter_ns()
                columns, rows = execute_fetch(cursor, query)
                elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
                checksum = result_checksum(columns, rows)
                if reference_checksum is None:
                    reference_columns, reference_rows, reference_checksum = columns, rows, checksum
                elif checksum != reference_checksum:
                    raise RuntimeError(
                        f"Result changed within the same run at iteration {iteration}; stop and investigate"
                    )
                timing_rows.append(
                    {
                        "case": args.case_id,
                        "stage": args.stage,
                        "iteration": iteration,
                        "elapsed_ms": round(elapsed_ms, 6),
                        "rows_returned": len(rows),
                        "sha256": checksum,
                    }
                )
            after = status_snapshot(cursor)

        if args.extended:
            snapshot(cursor, args.output, f'{stem}_after')
            global_delta(args.output, stem)

        with (args.output / f"{stem}_timings.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=timing_rows[0].keys())
            writer.writeheader()
            writer.writerows(timing_rows)
        write_status(args.output / f"{stem}_session_status.csv", before, after)
        assert reference_columns is not None and reference_rows is not None and reference_checksum is not None
        write_rows(args.output / f"{args.case_id}_results_{args.stage}.csv", reference_columns, reference_rows)

        values = [float(row["elapsed_ms"]) for row in timing_rows]
        summary = {
            "case": args.case_id,
            "stage": args.stage,
            "iterations": len(values),
            "warmups": args.warmups,
            "rows_returned": len(reference_rows),
            "sha256": reference_checksum,
            "min_ms": min(values),
            "mean_ms": statistics.fmean(values),
            "median_ms": statistics.median(values),
            "p95_ms_nearest_rank": percentile_nearest_rank(values, 0.95),
            "max_ms": max(values),
            "population_stdev_ms": statistics.pstdev(values),
        }
        (args.output / f"{stem}_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        try_performance_schema(
            cursor,
            args.output / f"{stem}_performance_schema.csv",
            query,
            f"ep2:{args.case_id}:{args.stage}:diagnostic",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"Evidence written to {args.output.resolve()}")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, MySQLError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
