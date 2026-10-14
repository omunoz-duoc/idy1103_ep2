#!/usr/bin/env python3
"""Safely create one EP2 experimental index, collect C evidence, then remove it."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:
    mysql = None
    MySQLError = Exception


INDEXES = {
    "Q1": (
        "idx_ep2_q1_store_status_ts",
        "ep2_orders",
        "CREATE INDEX idx_ep2_q1_store_status_ts "
        "ON ep2_orders(store_id, status, order_ts DESC, order_id DESC)",
        "fk_orders_store",
        "CREATE INDEX fk_orders_store ON ep2_orders(store_id)",
    ),
    "Q2": (
        "idx_ep2_q2_method_ts_amount",
        "ep2_payments",
        "CREATE INDEX idx_ep2_q2_method_ts_amount "
        "ON ep2_payments(method, paid_ts, amount)",
        None,
        None,
    ),
    "Q3": (
        "idx_ep2_q3_order_ts",
        "ep2_orders",
        "CREATE INDEX idx_ep2_q3_order_ts ON ep2_orders(order_ts, order_id)",
        None,
        None,
    ),
    "Q4": (
        "idx_ep2_q4_cust_status_ts",
        "ep2_orders",
        "CREATE INDEX idx_ep2_q4_cust_status_ts "
        "ON ep2_orders(customer_id, status, order_ts)",
        "fk_orders_customer",
        "CREATE INDEX fk_orders_customer ON ep2_orders(customer_id)",
    ),
    "Q5": (
        "idx_ep2_q5_store_ts_status_total",
        "ep2_orders",
        "CREATE INDEX idx_ep2_q5_store_ts_status_total "
        "ON ep2_orders(store_id, order_ts, status, total_amount)",
        "fk_orders_store",
        "CREATE INDEX fk_orders_store ON ep2_orders(store_id)",
    ),
}


def index_exists(cursor, database: str, table: str, index: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.statistics
        WHERE table_schema=%s AND table_name=%s AND index_name=%s
        """,
        (database, table, index),
    )
    return cursor.fetchone()[0] > 0


def cleanup_index(cursor, database: str, spec: tuple) -> None:
    index_name, table_name, _, support_name, support_sql = spec
    if not index_exists(cursor, database, table_name, index_name):
        print(f"Cleanup: {index_name} is already absent.", flush=True)
        return
    if support_name and not index_exists(cursor, database, table_name, support_name):
        print(
            f"Restoring foreign-key support index {support_name} before cleanup...",
            flush=True,
        )
        cursor.execute(support_sql)
    print(f"Removing {index_name} after the measurement...", flush=True)
    cursor.execute(f"DROP INDEX {index_name} ON {table_name}")
    if index_exists(cursor, database, table_name, index_name):
        raise RuntimeError(f"Cleanup verification failed: {index_name} still exists")
    print(f"Verified cleanup: {index_name} was removed.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create one experimental index, collect stage C, and remove the index."
    )
    parser.add_argument("--case", required=True, choices=tuple(INDEXES), type=str.upper)
    parser.add_argument("--params", type=Path, default=Path("sql/00_parametros.sql"))
    parser.add_argument("--output", type=Path, default=Path("evidencias"))
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--host", default=os.getenv("EP2_MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("EP2_MYSQL_PORT", "3306")))
    parser.add_argument("--user", default=os.getenv("EP2_MYSQL_USER", "root"))
    parser.add_argument("--database", default=os.getenv("EP2_MYSQL_DATABASE", "ep2_lab"))
    parser.add_argument("--password-env", default="EP2_MYSQL_PASSWORD")
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="repair FK support if needed and remove this case's leftover index",
    )
    args = parser.parse_args()

    if mysql is None:
        print(
            "Missing dependency. Run: python3 -m pip install -r automation/requirements.txt",
            file=sys.stderr,
        )
        return 2
    password = os.getenv(args.password_env)
    if password is None:
        print(f"Set {args.password_env} before running.", file=sys.stderr)
        return 2

    spec = INDEXES[args.case]
    index_name, table_name, create_sql, _, _ = spec
    connection = mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=password,
        database=args.database,
        autocommit=True,
        connection_timeout=10,
    )
    created_here = False
    try:
        cursor = connection.cursor()
        if args.cleanup_only:
            cleanup_index(cursor, args.database, spec)
            return 0
        cursor.execute(
            """
            SELECT DISTINCT TABLE_NAME, INDEX_NAME
            FROM information_schema.statistics
            WHERE table_schema=%s AND INDEX_NAME LIKE 'idx_ep2_q%%'
            ORDER BY TABLE_NAME, INDEX_NAME
            """,
            (args.database,),
        )
        leftovers = cursor.fetchall()
        if leftovers:
            formatted = ", ".join(f"{table}.{index}" for table, index in leftovers)
            raise RuntimeError(
                "Experimental index already exists. Remove it before continuing: " + formatted
            )

        print(f"Creating {index_name} on {table_name}...", flush=True)
        cursor.execute(create_sql)
        created_here = True

        if not index_exists(cursor, args.database, table_name, index_name):
            raise RuntimeError(f"MySQL did not report {index_name} after CREATE INDEX")
        print(f"Verified: {index_name} exists. Collecting stage C...", flush=True)

        runner = Path(__file__).with_name("evidence_runner.py")
        query = Path("queries") / f"{args.case}_B.sql"
        command = [
            sys.executable,
            str(runner),
            "--case", args.case,
            "--stage", "C",
            "--query", str(query),
            "--params", str(args.params),
            "--output", str(args.output),
            "--iterations", str(args.iterations),
            "--warmups", str(args.warmups),
            "--host", args.host,
            "--port", str(args.port),
            "--user", args.user,
            "--database", args.database,
            "--password-env", args.password_env,
        ]
        subprocess.run(command, check=True)
        return 0
    finally:
        if created_here:
            cleanup_cursor = connection.cursor()
            cleanup_index(cleanup_cursor, args.database, spec)
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Stage-C evidence collection failed (exit {exc.returncode}).", file=sys.stderr)
        raise SystemExit(exc.returncode)
    except (OSError, RuntimeError, MySQLError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
