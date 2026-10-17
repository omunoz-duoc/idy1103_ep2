"""Read-only optional diagnostics. Missing privileges are evidence, not zero values."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import subprocess
from pathlib import Path

from evidence_runner import DATASET_TABLES, canonical_row, execute_fetch, write_rows


def save_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


class Diagnostics:
    def __init__(self, cursor, output: Path, stem: str):
        self.cursor = cursor
        self.output = output
        self.stem = stem
        self.status = {}

    def query(self, name: str, sql: str):
        try:
            columns, rows = execute_fetch(self.cursor, sql)
            write_rows(self.output / f'{self.stem}_{name}.csv', columns, rows)
            self.status[name] = {'available': True, 'rows': len(rows)}
            return rows
        except Exception as exc:
            self.status[name] = {'available': False, 'reason': f'{type(exc).__name__}: {exc}'}
            return None

    def finish(self):
        save_json(self.output / f'{self.stem}_availability.json', self.status)


def snapshot(cursor, output: Path, stem: str):
    collector = Diagnostics(cursor, output, stem)
    collector.query('timestamp', 'SELECT NOW(6) AS collected_at, CONNECTION_ID() AS connection_id')
    collector.query('global_status', """
        SHOW GLOBAL STATUS WHERE Variable_name IN (
          'Innodb_buffer_pool_read_requests','Innodb_buffer_pool_reads',
          'Innodb_data_reads','Innodb_data_read','Innodb_data_writes','Innodb_data_written',
          'Innodb_os_log_written','Threads_connected','Threads_running',
          'Created_tmp_tables','Created_tmp_disk_tables','Sort_rows','Select_scan',
          'Innodb_row_lock_waits','Innodb_row_lock_time','Uptime')
    """)
    collector.query('index_io', """
        SELECT OBJECT_NAME, INDEX_NAME, COUNT_STAR, SUM_TIMER_WAIT,
               COUNT_READ, SUM_TIMER_READ, COUNT_WRITE, SUM_TIMER_WRITE,
               COUNT_FETCH, COUNT_INSERT, COUNT_UPDATE, COUNT_DELETE
        FROM performance_schema.table_io_waits_summary_by_index_usage
        WHERE OBJECT_SCHEMA=DATABASE() ORDER BY OBJECT_NAME, INDEX_NAME
    """)
    collector.query('lock_waits', """
        SELECT COUNT(*) AS schema_lock_waits
        FROM performance_schema.data_lock_waits w
        JOIN performance_schema.data_locks l
          ON l.ENGINE=w.ENGINE AND l.ENGINE_LOCK_ID=w.REQUESTING_ENGINE_LOCK_ID
        WHERE l.OBJECT_SCHEMA=DATABASE()
    """)
    collector.query('connections', """
        SELECT ID, DB, COMMAND, TIME, STATE
        FROM information_schema.PROCESSLIST WHERE DB=DATABASE() ORDER BY ID
    """)
    collector.finish()


def global_delta(output: Path, stem: str):
    import csv
    paths = [output / f'{stem}_{when}_global_status.csv' for when in ('before', 'after')]
    if not all(path.exists() for path in paths):
        return
    snapshots = []
    for path in paths:
        with path.open(encoding='utf-8') as handle:
            snapshots.append({row['Variable_name']: row['Value'] for row in csv.DictReader(handle)})
    rows = []
    for name, before in snapshots[0].items():
        after = snapshots[1].get(name)
        if after is None:
            continue
        is_gauge = name in ('Threads_connected', 'Threads_running')
        delta = '' if is_gauge else int(after) - int(before)
        rows.append((name, before, after, delta, 'gauge' if is_gauge else 'counter'))
    write_rows(output / f'{stem}_global_delta.csv', ['metric', 'before', 'after', 'delta', 'kind'], rows)


def extra_plans(cursor, output: Path, stem: str, query: str):
    collector = Diagnostics(cursor, output, stem)
    collector.query('explain_traditional', f'EXPLAIN {query}')
    try:
        _, rows = execute_fetch(cursor, f'EXPLAIN FORMAT=JSON {query}')
        content = json.loads(rows[0][0])
        save_json(output / f'{stem}_explain.json', content)
        collector.status['explain_json'] = {'available': True}
    except Exception as exc:
        collector.status['explain_json'] = {'available': False, 'reason': str(exc)}
    collector.query('warnings', 'SHOW WARNINGS')
    collector.finish()


def index_sizes(cursor, output: Path, stem: str):
    collector = Diagnostics(cursor, output, stem)
    collector.query('index_pages', """
        SELECT table_name, index_name, stat_name, stat_value,
               @@innodb_page_size AS page_size_bytes,
               stat_value * @@innodb_page_size AS estimated_bytes,
               last_update
        FROM mysql.innodb_index_stats
        WHERE database_name=DATABASE() AND stat_name IN ('size','n_leaf_pages')
        ORDER BY table_name, index_name, stat_name
    """)
    collector.finish()


def environment(cursor, output: Path):
    collector = Diagnostics(cursor, output, 'mysql')
    collector.query('version', 'SELECT VERSION(), @@version_comment, NOW(), DATABASE()')
    collector.query('variables', """
        SHOW VARIABLES WHERE Variable_name IN (
          'performance_schema','innodb_buffer_pool_size','innodb_page_size',
          'cte_max_recursion_depth','max_connections','optimizer_switch','slow_query_log',
          'long_query_time','datadir','pid_file','port','hostname','server_uuid',
          'innodb_stats_persistent','innodb_stats_auto_recalc','innodb_stats_persistent_sample_pages')
    """)
    collector.query('consumers', """
        SELECT NAME, ENABLED FROM performance_schema.setup_consumers
        WHERE NAME LIKE 'events_statements%' OR NAME LIKE 'events_waits%'
    """)
    collector.query('instruments', """
        SELECT NAME, ENABLED, TIMED FROM performance_schema.setup_instruments
        WHERE NAME LIKE 'statement/sql/%' OR NAME LIKE 'wait/io/table/%'
    """)
    collector.query('grants', 'SHOW GRANTS FOR CURRENT_USER()')
    for table in DATASET_TABLES:
        collector.query(f'create_{table}', f'SHOW CREATE TABLE {table}')
    collector.query('orders_distribution', 'SELECT status, COUNT(*) AS n FROM ep2_orders GROUP BY status')
    collector.query('payments_distribution', 'SELECT method, COUNT(*) AS n FROM ep2_payments GROUP BY method')
    collector.query('customers_distribution', 'SELECT city, segment, COUNT(*) AS n FROM ep2_customers GROUP BY city, segment')
    collector.query('products_distribution', 'SELECT category, COUNT(*) AS n FROM ep2_products GROUP BY category')
    collector.query('stores_distribution', 'SELECT region, COUNT(*) AS n FROM ep2_stores GROUP BY region')
    collector.query('order_dates', 'SELECT MIN(order_ts), MAX(order_ts) FROM ep2_orders')
    collector.finish()


def fingerprint(cursor, output: Path):
    keys = dict(zip(DATASET_TABLES, ('customer_id', 'product_id', 'store_id', 'order_id', 'item_id', 'payment_id')))
    result = {}
    for table in DATASET_TABLES:
        cursor.execute(f'SELECT * FROM {table} ORDER BY {keys[table]}')
        digest = hashlib.sha256()
        digest.update(json.dumps([column[0] for column in cursor.description]).encode())
        count = 0
        while True:
            rows = cursor.fetchmany(1000)
            if not rows:
                break
            for row in rows:
                digest.update(canonical_row(row).encode('utf-8'))
                digest.update(b'\n')
                count += 1
        result[table] = {'rows': count, 'sha256': digest.hexdigest()}
    save_json(output, result)
    return result


def host_environment(output: Path, pid: int | None):
    commands = {
        'kernel': ['uname', '-a'],
        'cpu': ['lscpu'],
        'ram': ['free', '-b'],
        'disks': ['lsblk', '-o', 'NAME,TYPE,SIZE,ROTA,MODEL'],
        'filesystems': ['df', '-h', str(output)],
    }
    if pid:
        commands['mysql_process'] = ['ps', '-p', str(pid), '-o', 'pid,comm,nlwp,pcpu,pmem,rss,vsz,etime']
    status = {'platform': platform.platform(), 'collected_at': dt.datetime.now().astimezone().isoformat()}
    for name, command in commands.items():
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            (output / f'host_{name}.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
            status[name] = {'available': result.returncode == 0, 'exit_code': result.returncode}
        except (OSError, subprocess.TimeoutExpired) as exc:
            status[name] = {'available': False, 'reason': str(exc)}
    # Record OS limits as read-only evidence; cgroup files describe the collector's context.
    files = {
        'collector_cgroup_memory_max': Path('/sys/fs/cgroup/memory.max'),
        'collector_cgroup_cpu_max': Path('/sys/fs/cgroup/cpu.max'),
    }
    if pid:
        files.update(mysql_limits=Path(f'/proc/{pid}/limits'), mysql_cgroup=Path(f'/proc/{pid}/cgroup'))
    for name, path in files.items():
        try:
            (output / f'host_{name}.txt').write_text(path.read_text(), encoding='utf-8')
            status[name] = {'available': True, 'source': str(path)}
        except OSError as exc:
            status[name] = {'available': False, 'reason': str(exc)}
    save_json(output / 'host_availability.json', status)
