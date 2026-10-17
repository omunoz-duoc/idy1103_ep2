import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from os_monitor import ProcessMonitor, SudoSession


def snapshot(cpu=100, io=None):
    return {
        'pid': 123,
        'process_name': 'mysqld',
        'start_ticks': 12,
        'cpu_ticks': cpu,
        'clock_ticks_per_second': 100,
        'rss_kib': 1000,
        'io': io,
        'io_error': 'PermissionError' if io is None else None,
    }


class ProcessMonitorTests(unittest.TestCase):
    def monitor(self, path, snapshots):
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('pidstat', 1), 0]
        patches = (
            patch('os_monitor.process_snapshot', side_effect=snapshots),
            patch('os_monitor.subprocess.Popen', return_value=process),
            patch('os_monitor.time.sleep'),
            patch('os_monitor.time.perf_counter', side_effect=[10, 20]),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        return ProcessMonitor(123, 1, path, 'Q1_C'), process

    def test_cpu_and_disk_deltas_and_cleanup_on_success(self):
        before = snapshot(io={'read_bytes': 100, 'write_bytes': 10, 'cancelled_write_bytes': 0})
        after = snapshot(cpu=150, io={'read_bytes': 300, 'write_bytes': 30, 'cancelled_write_bytes': 0})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            monitor, process = self.monitor(path, [before, before, after])
            with monitor:
                pass
            data = json.loads((path / 'Q1_C_os_metadata.json').read_text())
            self.assertEqual(data['cpu_seconds'], 0.5)
            self.assertEqual(data['cpu_percent_one_core'], 5)
            self.assertEqual(data['disk_io_delta_bytes']['read_bytes'], 200)
            self.assertTrue(data['batch_succeeded'])
            process.terminate.assert_called_once()

    def test_query_failure_stops_monitor_and_missing_io_stays_null(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            monitor, process = self.monitor(path, [snapshot(), snapshot(), snapshot()])
            with self.assertRaisesRegex(RuntimeError, 'query failed'):
                with monitor:
                    raise RuntimeError('query failed')
            data = json.loads((path / 'Q1_C_os_metadata.json').read_text())
            self.assertIsNone(data['disk_io_delta_bytes'])
            self.assertFalse(data['batch_succeeded'])
            process.terminate.assert_called_once()

    def test_disabled_monitor_does_not_launch_pidstat(self):
        with patch('os_monitor.subprocess.Popen') as popen:
            with ProcessMonitor(None, 1, Path('/unused'), 'Q1_A'):
                pass
            popen.assert_not_called()

    def test_sudo_authorization_happens_before_sampler_and_is_stopped_on_startup_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            process = Mock()
            process.poll.return_value = 1
            session = Mock()
            events = []
            session.start.side_effect = lambda: events.append('authorize')
            with patch('os_monitor.SudoSession', return_value=session), \
                 patch('os_monitor.process_snapshot', return_value=snapshot()), \
                 patch('os_monitor.time.sleep'), \
                 patch('os_monitor.subprocess.Popen', side_effect=lambda *a, **kw: (events.append('sampler') or process)):
                with self.assertRaisesRegex(RuntimeError, 'pidstat terminó'):
                    with ProcessMonitor(123, 1, Path(folder), 'Q1_A', privileged=True):
                        pass
            self.assertEqual(events, ['authorize', 'sampler'])
            session.stop.assert_called_once()

    def test_sudo_refresh_is_noninteractive(self):
        session = SudoSession()
        session.stop_event = Mock()
        session.stop_event.wait.side_effect = [False, True]
        with patch('os_monitor.subprocess.run', return_value=Mock(returncode=0)) as run:
            session.refresh()
        run.assert_called_once_with(['sudo', '-n', '-v'], capture_output=True, text=True, timeout=10)

    def test_cancelled_sudo_does_not_launch_refresh_thread(self):
        session = SudoSession()
        with patch('os_monitor.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'sudo')), \
             patch('os_monitor.threading.Thread') as thread:
            with self.assertRaisesRegex(RuntimeError, 'usuario Linux'):
                session.start()
        thread.assert_not_called()


if __name__ == '__main__':
    unittest.main()
