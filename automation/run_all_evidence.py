#!/usr/bin/env python3
"""Sequential Q1-Q5 experiment suite with recoverable cleanup and audit artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from evidence_layout import ROOT, CASES, clean_evidence, suite_lock
from evidence_runner import read_params, read_query, write_indexes, write_table_sizes, execute_fetch, write_rows
from extra_evidence import environment, fingerprint, host_environment, index_sizes, save_json
from run_stage_c import INDEXES, cleanup_index, index_exists
from summarize_evidence import summarize


def connect():
    import mysql.connector
    return mysql.connector.connect(
        host=os.getenv('EP2_MYSQL_HOST', '127.0.0.1'),
        port=int(os.getenv('EP2_MYSQL_PORT', '3306')),
        user=os.getenv('EP2_MYSQL_USER', 'root'),
        password=os.environ['EP2_MYSQL_PASSWORD'],
        database=os.getenv('EP2_MYSQL_DATABASE', 'ep2_lab'),
        autocommit=True, connection_timeout=10, charset='utf8mb4',
    )


def assert_original_indexes(cursor):
    cursor.execute('SELECT DISTINCT INDEX_NAME FROM information_schema.statistics WHERE TABLE_SCHEMA=DATABASE()')
    leftovers = [row[0] for row in cursor.fetchall() if row[0].startswith('idx_ep2_q')]
    if leftovers:
        raise RuntimeError('Hay índices experimentales residuales: ' + ', '.join(leftovers))


def index_definition(cursor):
    cursor.execute('''SELECT TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX, COLUMN_NAME, COLLATION,
                            NON_UNIQUE, INDEX_TYPE
                      FROM information_schema.statistics WHERE TABLE_SCHEMA=DATABASE()
                      ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX''')
    return cursor.fetchall()


def cooldown(seconds: int, log):
    if seconds:
        log(f'Cooldown: {seconds} s (se conserva la caché de MySQL).')
    remaining = seconds
    while remaining:
        step = min(remaining, 5)
        time.sleep(step)
        remaining -= step


def run_command(command: list[str], path: Path):
    # Drain stdout while running so progress remains visible and the log is complete.
    with path.open('w', encoding='utf-8') as handle:
        # Keep the terminal/session: sudo timestamps are normally scoped to the TTY.
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for line in process.stdout:
                print(line, end='', flush=True)
                handle.write(line)
                handle.flush()
            code = process.wait()
            if code:
                raise RuntimeError(f'Falló un runner (exit {code}); consulte {path}')
        except BaseException:
            if process.poll() is None:
                # Ctrl+C already reaches the foreground child. Give it time to stop
                # its sampler before sending another signal (e.g. on parent SIGTERM).
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.send_signal(signal.SIGINT)
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            raise
        finally:
            process.stdout.close()


def validate_results(folder: Path):
    records = {}
    for path in folder.glob('*/**/Q*_summary.json'):
        profile = path.parent.name
        if profile not in ('micro', 'carga'):
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        records[(data['stage'], profile)] = data
    baseline = records.get(('A', 'micro'))
    if baseline is None:
        raise RuntimeError('Falta la referencia A/micro')
    for key, data in records.items():
        if (data['sha256'], data['rows_returned']) != (baseline['sha256'], baseline['rows_returned']):
            raise RuntimeError(f'Los resultados cambiaron en {folder.name} {key}')
    save_json(folder / 'equivalencia.json', {
        'same_results': True, 'sha256': baseline['sha256'],
        'rows_returned': baseline['rows_returned'],
        'validated_batches': [f'{stage}/{profile}' for stage, profile in sorted(records)],
        'scope': 'Multiconjunto tipado de filas; los CSV conservan el orden de salida.',
    })


def integrity_manifest(output: Path):
    rows = []
    for path in sorted(output.rglob('*')):
        if path.is_file() and path.name != 'integridad_sha256.csv':
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append((str(path.relative_to(output)), path.stat().st_size, digest))
    write_rows(output / 'integridad_sha256.csv', ['file', 'bytes', 'sha256'], rows)


def write_review_report(output: Path):
    lines = ['# Cobertura de la recolección', '',
             'Los archivos availability.json indican disponibilidad; sin permisos no significa cero.', '']
    for path in sorted(output.rglob('*availability.json')):
        unavailable = [name for name, value in json.loads(path.read_text()).items()
                       if isinstance(value, dict) and value.get('available') is False]
        if unavailable:
            lines.append(f"- `{path.relative_to(output)}`: no disponible {', '.join(unavailable)}.")
    for path in sorted(output.rglob('*performance_schema.status.json')):
        status = json.loads(path.read_text())
        if not status.get('available'):
            lines.append(f"- `{path.relative_to(output)}`: {status.get('reason')}.")
    for path in sorted(output.rglob('*os_metadata.json')):
        data = json.loads(path.read_text())
        if data.get('short_batch'):
            lines.append(f'- `{path.relative_to(output)}`: lote corto, aumentar iteraciones por igual en A/B/C.')
        if data.get('disk_io_delta_bytes') is None:
            lines.append(f'- `{path.relative_to(output)}`: I/O físico no disponible.')
    for path in sorted(output.rglob('*_summary.json')):
        data = json.loads(path.read_text())
        if data.get('rows_returned') == 0:
            lines.append(f'- `{path.relative_to(output)}`: resultado vacío; revisar selectividad antes de concluir.')
    lines.extend(['', '## Límites del experimento', '',
                  '- Secuencia fija A/B/C y caché caliente; el cooldown no vacía el buffer pool.',
                  '- Carga con un cliente secuencial; no demuestra escalabilidad concurrente.',
                  '- Los snapshots globales y por índice pueden incluir otras sesiones y consultas de diagnóstico.',
                  '- Las cifras de páginas de índices son estadísticas estimadas y pueden estar desactualizadas.',
                  '- Los tiempos DDL incluyen red y estadísticas automáticas de creación del índice.'])
    (output / 'COBERTURA.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (output / 'PENDIENTES_MANUALES.md').write_text(
        '# Evidencias y decisiones por completar\n\n'
        '- Capturas exigidas por la pauta, con consulta/etapa y fecha: __________________\n'
        '- Concurrencia conocida, equipo real, límites Docker/WSL y actividad externa: __________________\n'
        '- Frecuencia de cada consulta y beneficio para el negocio: __________________\n'
        '- Costo de INSERT/UPDATE/DELETE en una copia de laboratorio: __________________\n'
        '- Pruebas con mayor volumen, concurrencia y secuencia intercalada: __________________\n'
        '- Interpretación causal de planes y conclusiones actualizadas a esta corrida: __________________\n\n'
        'Esta suite no altera datos de negocio ni ejecuta escrituras de prueba. '
        'Los documentos docs/consultas/Qn.md conservan conclusiones de su corrida histórica hasta revisión.\n',
        encoding='utf-8',
    )


def write_case_report(folder: Path):
    case = folder.name
    lines = [f'# Evidencias {case}', '',
             'Resumen automático de esta corrida. La interpretación causal se completa revisando los planes.', '',
             '| Perfil | Etapa | Iteraciones | Mediana ms | p95 ms | Evidencia |',
             '|---|---|---:|---:|---:|---|']
    for stage in ('A', 'B', 'C'):
        for profile in ('micro', 'carga'):
            path = folder / stage / profile / f'{case}_{stage}_summary.json'
            if not path.exists():
                continue
            data = json.loads(path.read_text())
            p95 = data.get('p95_ms_nearest_rank')
            lines.append(f"| {profile} | {stage} | {data['iterations']} | {data['median_ms']:.6f} | "
                         f"{p95 if p95 is not None else 'N/D'} | [resumen]({path.relative_to(folder)}) |")
    lines.extend(['', '- Equivalencia de resultados: [equivalencia.json](equivalencia.json).',
                  '- Comparar A→B para la reescritura y B→C para el efecto incremental del índice.',
                  '- Interpretación de los operadores y dos causas observadas: __________________',
                  '- Impacto de negocio, frecuencia y costo de escritura: __________________',
                  '- Capturas y condiciones manuales: __________________',
                  '- Los archivos availability.json y COBERTURA.md explican las métricas faltantes.'])
    (folder / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def parse_args():
    parser = argparse.ArgumentParser(description='Q1–Q5, A/B/C, microbenchmark y carga sostenida, con cooldown.')
    parser.add_argument('--clean', action='store_true', help='respaldar evidencias anteriores antes de empezar')
    parser.add_argument('--cooldown', type=int, default=10, help='segundos entre lotes; predeterminado 10')
    parser.add_argument('--iterations', type=int, default=30, help='iteraciones del microbenchmark; predeterminado 30')
    parser.add_argument('--load-iterations', type=int, default=10000, help='iteraciones de carga; predeterminado 10000')
    parser.add_argument('--warmups', type=int, default=2)
    parser.add_argument('--interval', type=int, default=1)
    parser.add_argument('--pid', type=int)
    parser.add_argument('--sudo-monitor', action='store_true', help='sudo solo para pidstat y /proc/PID/io')
    parser.add_argument('--skip-load', action='store_true', help='solo microbenchmark; sin muestras OS')
    parser.add_argument('--params', type=Path, default=ROOT / 'sql/00_parametros.sql')
    parser.add_argument('--analyze-initial', action='store_true', help='ANALYZE TABLE una vez antes de A (requiere permisos)')
    parser.add_argument('--dry-run', action='store_true', help='mostrar plan sin conectar, mover archivos ni ejecutar SQL')
    args = parser.parse_args()
    if min(args.iterations, args.load_iterations, args.interval) < 1 or min(args.cooldown, args.warmups) < 0:
        parser.error('Iteraciones e intervalo deben ser positivos; cooldown y warmups >= 0')
    if args.pid is not None and args.pid < 1:
        parser.error('--pid debe ser positivo')
    return args


def execute_suite(args):
    output = ROOT / 'evidencias'
    for case in CASES:
        for stage in ('A', 'B', 'C'):
            print(f'{case}/{stage}: micro={args.iterations}, carga={0 if args.skip_load else args.load_iterations}; cooldown={args.cooldown}s')
    if args.dry_run:
        print('Plan únicamente. --clean respaldaría las carpetas activas en evidencias_respaldos/.')
        return

    if output.is_symlink():
        raise RuntimeError('evidencias no puede ser un enlace simbólico')
    if output.exists() and not args.clean and any(path.is_symlink() for path in output.rglob('*')):
        raise RuntimeError('Hay enlaces simbólicos dentro de evidencias; use una carpeta activa ordinaria')

    if 'EP2_MYSQL_PASSWORD' not in os.environ:
        raise RuntimeError('Exporte EP2_MYSQL_PASSWORD en esta terminal')
    params_text = args.params.read_text(encoding='utf-8')
    read_params(args.params)
    for case in CASES:
        for stage in ('A', 'B'):
            read_query(ROOT / 'queries' / f'{case}_{stage}.sql')

    pid = args.pid
    if not args.skip_load:
        if os.getenv('EP2_MYSQL_HOST', '127.0.0.1') not in ('localhost', '127.0.0.1', '::1'):
            raise RuntimeError('El monitoreo OS debe ejecutarse en el host de MySQL con conexión local')
        if not shutil.which('pidstat'):
            raise RuntimeError('Instale pidstat: sudo apt install sysstat')
        if pid is None:
            result = subprocess.run(['pgrep', '-x', 'mysqld'], capture_output=True, text=True)
            candidates = result.stdout.split()
            if len(candidates) != 1:
                raise RuntimeError('No se detectó un único mysqld; especifique --pid NUMERO')
            pid = int(candidates[0])
        if (Path('/proc') / str(pid) / 'comm').read_text().strip() != 'mysqld':
            raise RuntimeError('El PID no pertenece a mysqld')
        if args.sudo_monitor:
            subprocess.run(['sudo', '-v'], check=True)

    connection = connect()
    try:
        cursor = connection.cursor()
        assert_original_indexes(cursor)
        original_definition = index_definition(cursor)
        # Refuse overwrites; --clean is explicit and only runs after connection validation.
        if output.exists() and any(path.is_file() for path in output.rglob('*')) and not args.clean:
            raise RuntimeError('Ya existen evidencias. Use --clean para respaldarlas y comenzar una corrida completa')
        backup = clean_evidence(ROOT) if args.clean else None
        env_folder = output / 'entorno'
        env_folder.mkdir(parents=True, exist_ok=True)
        (env_folder / '00_parametros.sql').write_text(params_text, encoding='utf-8')
        params_path = env_folder / '00_parametros.sql'
        config = {**vars(args), 'pid': pid, 'python': sys.version, 'started_at': dt.datetime.now().astimezone().isoformat(),
                  'status': 'running', 'backup': str(backup) if backup else None}
        save_json(output / 'ejecucion.json', config)
        with (output / 'maestro.log').open('w', encoding='utf-8') as log_handle:
            def log(message):
                line = f'[{dt.datetime.now().astimezone().isoformat()}] {message}'
                print(line, flush=True)
                log_handle.write(line + '\n')
                log_handle.flush()
            try:
                host_environment(env_folder, pid)
                environment(cursor, env_folder)
                fingerprint_before = fingerprint(cursor, env_folder / 'dataset_before.json')
                expected = {'ep2_customers': 5000, 'ep2_products': 2000, 'ep2_stores': 20,
                            'ep2_orders': 20000, 'ep2_order_items': 100000, 'ep2_payments': 15000}
                if any(fingerprint_before[table]['rows'] != count for table, count in expected.items()):
                    raise RuntimeError('Conteos del dataset incorrectos; consulte entorno/dataset_before.json')
                if args.analyze_initial:
                    columns, rows = execute_fetch(cursor, 'ANALYZE TABLE ' + ','.join(expected))
                    write_rows(env_folder / 'analyze_initial.csv', columns, rows)
                    if any(str(row[-2]).lower() == 'error' for row in rows):
                        raise RuntimeError('Falló ANALYZE TABLE; consulte analyze_initial.csv')
                sources = {}
                for path in [ROOT / 'dataset.sql', *sorted((ROOT / 'queries').glob('*.sql')), *sorted((ROOT / 'automation').glob('*.py')), *sorted((ROOT / 'automation').glob('*.sh'))]:
                    sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
                save_json(env_folder / 'fuentes_sha256.json', sources)

                for case in CASES:
                    case_folder = output / case
                    case_folder.mkdir(exist_ok=True)
                    for stage in ('A', 'B', 'C'):
                        assert_original_indexes(cursor)
                        if index_definition(cursor) != original_definition:
                            raise RuntimeError('El inventario de índices cambió entre experimentos')
                        stage_folder = case_folder / stage
                        stage_folder.mkdir()
                        spec = INDEXES[case]
                        created = False
                        ddl = {'case': case, 'sql': spec[2], 'created': False, 'cleanup_succeeded': False}
                        try:
                            if stage == 'C':
                                write_indexes(cursor, stage_folder / 'indices_before.csv', os.getenv('EP2_MYSQL_DATABASE', 'ep2_lab'))
                                write_table_sizes(cursor, stage_folder / 'table_sizes_before.csv', os.getenv('EP2_MYSQL_DATABASE', 'ep2_lab'))
                                index_sizes(cursor, stage_folder, 'before')
                                log(f'{case}/C: creando {spec[0]}')
                                started = time.perf_counter()
                                cursor.execute(spec[2])
                                created = True
                                ddl.update(created=True, create_elapsed_ms=(time.perf_counter() - started) * 1000)
                                if not index_exists(cursor, os.getenv('EP2_MYSQL_DATABASE', 'ep2_lab'), spec[1], spec[0]):
                                    raise RuntimeError('No se verificó la creación del índice')
                                write_indexes(cursor, stage_folder / 'indices_with_experiment.csv', os.getenv('EP2_MYSQL_DATABASE', 'ep2_lab'))
                                index_sizes(cursor, stage_folder, 'with_experiment')
                            for profile, count in [('micro', args.iterations), *([] if args.skip_load else [('carga', args.load_iterations)])]:
                                cooldown(args.cooldown, log)
                                folder = stage_folder / profile
                                folder.mkdir()
                                command = [sys.executable, '-u', str(ROOT / 'automation/evidence_runner.py'),
                                           '--case', case, '--stage', stage,
                                           '--query', str(ROOT / 'queries' / f"{case}_{'A' if stage == 'A' else 'B'}.sql"),
                                           '--params', str(params_path), '--output', str(folder),
                                           '--iterations', str(count), '--warmups', str(args.warmups), '--extended']
                                if profile == 'carga':
                                    command.extend(['--pidstat-pid', str(pid), '--pidstat-interval', str(args.interval)])
                                    if args.sudo_monitor:
                                        command.append('--pidstat-sudo')
                                log(f'{case}/{stage}/{profile}: {count} iteraciones')
                                run_command(command, folder / 'runner.log')
                                validate_results(case_folder)
                        finally:
                            if stage == 'C':
                                try:
                                    if created:
                                        ddl['support_index_restored'] = bool(spec[3]) and not index_exists(
                                            cursor, os.getenv('EP2_MYSQL_DATABASE', 'ep2_lab'), spec[1], spec[3])
                                        cleanup_started = time.perf_counter()
                                        cleanup_index(cursor, os.getenv('EP2_MYSQL_DATABASE', 'ep2_lab'), spec)
                                        ddl['cleanup_elapsed_ms'] = (time.perf_counter() - cleanup_started) * 1000
                                        ddl['cleanup_succeeded'] = True
                                        write_indexes(cursor, stage_folder / 'indices_after_cleanup.csv', os.getenv('EP2_MYSQL_DATABASE', 'ep2_lab'))
                                        assert_original_indexes(cursor)
                                        if index_definition(cursor) != original_definition:
                                            raise RuntimeError('La limpieza no restauró los índices originales')
                                finally:
                                    save_json(stage_folder / 'ddl.json', ddl)
                    log(f'{case}: A/B/C completados con resultados equivalentes')
                    write_case_report(case_folder)

                after = fingerprint(cursor, env_folder / 'dataset_after.json')
                save_json(env_folder / 'dataset_equivalence.json', {'unchanged': fingerprint_before == after})
                if fingerprint_before != after:
                    raise RuntimeError('El dataset cambió durante los experimentos; no se acepta la comparación')
                summarize(output, output / 'comparacion_micro.csv', 'micro')
                if not args.skip_load:
                    summarize(output, output / 'comparacion_carga.csv', 'carga')
                config['status'] = 'complete'
                log('Suite completa. Los contadores globales/OS pueden incluir actividad de otras sesiones.')
            except BaseException as exc:
                config['status'] = 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed'
                config['error'] = f'{type(exc).__name__}: {exc}'
                log(f"Suite detenida: {config['error']}")
                raise
            finally:
                config['finished_at'] = dt.datetime.now().astimezone().isoformat()
                save_json(output / 'ejecucion.json', config)
                write_review_report(output)
                integrity_manifest(output)
    finally:
        connection.close()


def main():
    args = parse_args()
    if args.dry_run:
        execute_suite(args)
        return
    def interrupted(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    with suite_lock():
        execute_suite(args)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        raise SystemExit(f'ERROR: {type(exc).__name__}: {exc}')
