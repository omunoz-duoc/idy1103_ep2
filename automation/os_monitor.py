"""Sample a local MySQL process only around the measured query batch."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import threading
import time
from pathlib import Path


class SudoSession:
    """Authorize on the inherited terminal and refresh without storing a password."""

    def __init__(self):
        self.stop_event = threading.Event()
        self.errors = []
        self.thread = None

    def start(self):
        try:
            # Runs before the benchmark and can prompt on the user's terminal.
            subprocess.run(['sudo', '-v'], check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RuntimeError(
                'No se pudo autorizar sudo para monitorear. Ingrese la contraseña '
                'de su usuario Linux en una terminal interactiva, o quite --sudo-monitor.'
            ) from exc
        self.thread = threading.Thread(target=self.refresh, daemon=True, name='ep2-sudo-refresh')
        self.thread.start()

    def refresh(self):
        while not self.stop_event.wait(30):
            try:
                result = subprocess.run(['sudo', '-n', '-v'], capture_output=True, text=True, timeout=10)
                if result.returncode:
                    self.errors.append(result.stderr.strip() or f'sudo exit {result.returncode}')
            except (OSError, subprocess.TimeoutExpired) as exc:
                self.errors.append(str(exc))

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=11)


def process_snapshot(pid: int, privileged: bool = False) -> dict:
    """Read process-wide counters; unavailable disk counters remain null."""
    proc = Path('/proc') / str(pid)
    stat = (proc / 'stat').read_text()
    # The command in parentheses can contain spaces; fields after it start at 3.
    fields = stat[stat.rfind(')') + 2:].split()
    status = {}
    for line in (proc / 'status').read_text().splitlines():
        name, _, value = line.partition(':')
        status[name] = value.strip()
    io = None
    io_error = None
    try:
        if privileged:
            io_text = subprocess.run(
                ['sudo', '-n', 'cat', str(proc / 'io')],
                check=True, capture_output=True, text=True,
            ).stdout
        else:
            io_text = (proc / 'io').read_text()
        io = {
            name: int(value.strip())
            for name, value in (
                line.split(':', 1) for line in io_text.splitlines()
            )
        }
    except (OSError, subprocess.CalledProcessError) as exc:
        io_error = f'{type(exc).__name__}: {exc}'
    return {
        'pid': pid,
        'process_name': status.get('Name'),
        'start_ticks': int(fields[19]),
        'cpu_ticks': int(fields[11]) + int(fields[12]),
        'clock_ticks_per_second': os.sysconf('SC_CLK_TCK'),
        'rss_kib': int(status['VmRSS'].split()[0]) if 'VmRSS' in status else None,
        'io': io,
        'io_error': io_error,
    }


class ProcessMonitor:
    def __init__(self, pid: int | None, interval: int, output: Path, stem: str, privileged: bool = False):
        self.pid = pid
        self.interval = interval
        self.output = output
        self.stem = stem
        self.privileged = privileged
        self.process = None
        self.log = None
        self.sudo_session = None

    def __enter__(self):
        if self.pid is None:
            return self
        try:
            if self.privileged:
                self.sudo_session = SudoSession()
                self.sudo_session.start()
            self.before = process_snapshot(self.pid, self.privileged)
            if self.before['process_name'] not in ('mysqld', 'mariadbd'):
                raise RuntimeError('El PID indicado no corresponde a mysqld/mariadbd')
            self.log = (self.output / f'{self.stem}_os_pidstat.txt').open('w', encoding='utf-8')
            command = ['pidstat', '-H', '-h', '-u', '-r', '-d', '-w', '-p', str(self.pid), str(self.interval)]
            if self.privileged:
                command = ['sudo', '-n', *command]
            self.process = subprocess.Popen(
                command,
                stdout=self.log,
                stderr=subprocess.STDOUT,
                env={**os.environ, 'LC_ALL': 'C', 'S_COLORS': 'never'},
            )
            # Give pidstat time to establish its first snapshot before the queries.
            time.sleep(0.15)
            if self.process.poll() is not None:
                self.log.flush()
                details = Path(self.log.name).read_text(encoding='utf-8').strip()
                raise RuntimeError(f'pidstat terminó al iniciar: {details}; consulte {self.log.name}')
            self.before = process_snapshot(self.pid, self.privileged)
            self.started_at = dt.datetime.now().astimezone().isoformat()
            self.started = time.perf_counter()
            print(f'Monitoreando PID {self.pid}; intervalo {self.interval} s.', flush=True)
        except BaseException:
            self.stop()
            raise
        return self

    def stop(self):
        try:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
        finally:
            if self.log is not None:
                self.log.close()
            if self.sudo_session is not None:
                self.sudo_session.stop()

    def __exit__(self, exc_type, exc, traceback):
        if self.pid is None:
            return False
        elapsed = time.perf_counter() - self.started
        ended_at = dt.datetime.now().astimezone().isoformat()
        try:
            after = process_snapshot(self.pid, self.privileged)
            same_process = after['start_ticks'] == self.before['start_ticks']
            sampler_alive = self.process.poll() is None
            # Allow a final sample covering the end of the query batch.
            if sampler_alive:
                try:
                    self.process.wait(timeout=self.interval + 0.15)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            self.stop()

        cpu_seconds = (
            (after['cpu_ticks'] - self.before['cpu_ticks']) / after['clock_ticks_per_second']
            if same_process else None
        )
        io_delta = None
        if same_process and self.before['io'] is not None and after['io'] is not None:
            io_delta = {
                key: after['io'][key] - self.before['io'][key]
                for key in ('read_bytes', 'write_bytes', 'cancelled_write_bytes')
            }
        metadata = {
            'scope': 'Proceso MySQL completo durante el lote; puede incluir otras sesiones.',
            'started_at': self.started_at,
            'ended_at': ended_at,
            'batch_elapsed_seconds': elapsed,
            'sample_interval_seconds': self.interval,
            'monitor_with_sudo': self.privileged,
            'sudo_refresh_errors': self.sudo_session.errors if self.sudo_session is not None else [],
            'sample_edges': 'pidstat incluye hasta un intervalo posterior al lote; usar timestamps.',
            'pidstat_running_at_batch_end': sampler_alive,
            'same_process_at_end': same_process,
            'batch_succeeded': exc_type is None,
            'short_batch': elapsed < 5 * self.interval,
            'cpu_seconds': cpu_seconds,
            'cpu_percent_one_core': 100 * cpu_seconds / elapsed if cpu_seconds is not None and elapsed else None,
            'disk_io_delta_bytes': io_delta,
            'before': self.before,
            'after': after,
            'limitations': [
                'CPU e I/O corresponden al proceso completo, no exclusivamente a una sentencia.',
                'El lote incluye transferencia, checksum del cliente y snapshots de sesión.',
                'RSS inicial/final y muestras pidstat no representan memoria exclusiva de la consulta.',
                'I/O físico puede ser cero por caché; null significa falta de permisos/datos.',
                'La resolución de CPU está limitada por los ticks del sistema operativo.',
            ],
        }
        path = self.output / f'{self.stem}_os_metadata.json'
        path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if metadata['short_batch']:
            print('AVISO: lote menor que 5 intervalos; repita A/B/C con más iteraciones.', flush=True)
        if io_delta is None:
            print('AVISO: I/O físico no disponible; consulte io_error en los metadatos.', flush=True)
        if not same_process or not sampler_alive:
            raise RuntimeError(f'Proceso o monitor interrumpido; consulte {path}')
        return False
