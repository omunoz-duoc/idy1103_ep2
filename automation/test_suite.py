import argparse
import contextlib
import io
import json
import os
import shutil
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import evidence_layout
import run_all_evidence as suite
from extra_evidence import Diagnostics
from summarize_evidence import summarize


class LayoutTests(unittest.TestCase):
    def test_cleanup_archives_every_target_and_recreates_case_folders(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('evidencias', 'evidencias_carga'):
                (root / name).mkdir()
                (root / name / 'sample.txt').write_text('original')
            (root / 'resultados_comparativos.csv').write_text('csv')
            with contextlib.redirect_stdout(io.StringIO()):
                backup = evidence_layout.clean_evidence(root)
            self.assertEqual((backup / 'evidencias/sample.txt').read_text(), 'original')
            self.assertEqual((backup / 'evidencias_carga/sample.txt').read_text(), 'original')
            self.assertEqual((backup / 'resultados_comparativos.csv').read_text(), 'csv')
            self.assertTrue((root / 'evidencias/Q5').is_dir())
            self.assertFalse((root / 'evidencias/sample.txt').exists())

    def test_cleanup_dry_run_and_symlink_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'evidencias').mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                evidence_layout.clean_evidence(root, dry_run=True)
            self.assertFalse((root / 'evidencias_respaldos').exists())
            (root / 'evidencias').rmdir()
            (root / 'evidencias').symlink_to(root / 'outside', target_is_directory=True)
            with self.assertRaises(RuntimeError):
                evidence_layout.clean_evidence(root)

    def test_organize_preserves_existing_query_and_load_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'evidencias').mkdir()
            (root / 'evidencias/Q1_A_summary.json').write_text('sample')
            (root / 'evidencias/01_dataset.txt').write_text('counts')
            load = root / 'evidencias_carga/Q2_C_old'
            load.mkdir(parents=True)
            (load / 'os.txt').write_text('cpu')
            with contextlib.redirect_stdout(io.StringIO()):
                evidence_layout.organize_evidence(root)
            self.assertEqual((root / 'evidencias/Q1/Q1_A_summary.json').read_text(), 'sample')
            self.assertEqual((root / 'evidencias/entorno/01_dataset.txt').read_text(), 'counts')
            self.assertEqual((root / 'evidencias/Q2/carga_historica/Q2_C_old/os.txt').read_text(), 'cpu')

    def test_exclusive_suite_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            with evidence_layout.suite_lock(Path(folder)):
                with self.assertRaises(RuntimeError):
                    with evidence_layout.suite_lock(Path(folder)):
                        pass


class SuiteTests(unittest.TestCase):
    def test_runner_preserves_terminal_session_for_sudo(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'runner.log'
            with contextlib.redirect_stdout(io.StringIO()):
                suite.run_command([sys.executable, '-c', 'import os; print(os.getsid(0))'], log)
            self.assertEqual(int(log.read_text().strip()), os.getsid(0))

    def make_fixture(self, root, fail_c=False):
        shutil.copytree(evidence_layout.ROOT / 'queries', root / 'queries')
        shutil.copyfile(evidence_layout.ROOT / 'dataset.sql', root / 'dataset.sql')
        (root / 'sql').mkdir()
        (root / 'sql/00_parametros.sql').write_text("SET @end_ts := '2026-10-14 00:00:00';")
        args = argparse.Namespace(
            iterations=3, load_iterations=5, interval=1, cooldown=0, warmups=2,
            pid=123, skip_load=False, sudo_monitor=False, clean=False,
            params=root / 'sql/00_parametros.sql', analyze_initial=False, dry_run=False,
        )
        connection = Mock()
        events = []
        connection.cursor.return_value.execute.side_effect = lambda sql: events.append(('sql', sql))
        counts = {'ep2_customers': 5000, 'ep2_products': 2000, 'ep2_stores': 20,
                  'ep2_orders': 20000, 'ep2_order_items': 100000, 'ep2_payments': 15000}

        def dataset(cursor, path):
            data = {table: {'rows': count, 'sha256': 'same'} for table, count in counts.items()}
            suite.save_json(path, data)
            return data

        def batch(command, path):
            case = command[command.index('--case') + 1]
            stage = command[command.index('--stage') + 1]
            profile = path.parent.name
            events.append(('batch', case, stage, profile))
            if fail_c and stage == 'C':
                raise RuntimeError('simulated batch failure')
            iterations = int(command[command.index('--iterations') + 1])
            suite.save_json(path.parent / f'{case}_{stage}_summary.json', dict(
                case=case, stage=stage, iterations=iterations, warmups=2,
                rows_returned=1, sha256='same', median_ms=1.0,
            ))

        patches = {
            'ROOT': root, 'connect': Mock(return_value=connection),
            'assert_original_indexes': Mock(), 'index_definition': Mock(return_value=['original']),
            'fingerprint': dataset, 'environment': Mock(), 'host_environment': Mock(),
            'write_indexes': Mock(), 'write_table_sizes': Mock(), 'index_sizes': Mock(),
            'run_command': batch, 'index_exists': Mock(return_value=True),
            'cleanup_index': Mock(side_effect=lambda cursor, db, spec: events.append(('cleanup', spec[0]))),
        }
        return args, patches, events

    def run_fixture(self, root, fail_c=False):
        args, replacements, events = self.make_fixture(root, fail_c)
        real_read = Path.read_text

        def read(path, *args, **kwargs):
            if path == Path('/proc/123/comm'):
                return 'mysqld\n'
            return real_read(path, *args, **kwargs)

        with patch.multiple(suite, **replacements), \
             patch.dict('os.environ', {'EP2_MYSQL_PASSWORD': 'test'}), \
             patch('run_all_evidence.shutil.which', return_value='/usr/bin/pidstat'), \
             patch.object(Path, 'read_text', read), contextlib.redirect_stdout(io.StringIO()):
            if fail_c:
                with self.assertRaisesRegex(RuntimeError, 'simulated batch failure'):
                    suite.execute_suite(args)
            else:
                suite.execute_suite(args)
        return events

    def test_all_five_cases_two_profiles_equivalence_and_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            events = self.run_fixture(root)
            batches = [event for event in events if event[0] == 'batch']
            expected = [('batch', case, stage, profile) for case in suite.CASES
                        for stage in ('A', 'B', 'C') for profile in ('micro', 'carga')]
            self.assertEqual(batches, expected)
            self.assertEqual(sum(event[0] == 'cleanup' for event in events), 5)
            for case in suite.CASES:
                spec = suite.INDEXES[case]
                self.assertLess(events.index(('sql', spec[2])), events.index(('batch', case, 'C', 'micro')))
                self.assertLess(events.index(('batch', case, 'C', 'carga')), events.index(('cleanup', spec[0])))
            self.assertEqual(json.loads((root / 'evidencias/ejecucion.json').read_text())['status'], 'complete')
            self.assertTrue((root / 'evidencias/comparacion_micro.csv').exists())
            self.assertTrue((root / 'evidencias/comparacion_carga.csv').exists())
            self.assertTrue((root / 'evidencias/integridad_sha256.csv').exists())

    def test_failed_c_batch_is_cleaned_and_audited(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            events = self.run_fixture(root, fail_c=True)
            self.assertIn(('cleanup', 'idx_ep2_q1_store_status_ts'), events)
            self.assertFalse(any(event[:2] == ('batch', 'Q2') for event in events))
            self.assertEqual(json.loads((root / 'evidencias/ejecucion.json').read_text())['status'], 'failed')
            self.assertTrue((root / 'evidencias/integridad_sha256.csv').exists())

    def test_optional_diagnostics_record_permission_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            cursor = Mock()
            cursor.execute.side_effect = RuntimeError('SELECT denied')
            collector = Diagnostics(cursor, Path(folder), 'sample')
            self.assertIsNone(collector.query('index_io', 'SELECT anything'))
            collector.finish()
            data = json.loads((Path(folder) / 'sample_availability.json').read_text())
            self.assertFalse(data['index_io']['available'])

    def test_result_mismatch_fails_comparison(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for stage, digest in [('A', 'one'), ('B', 'two')]:
                output = root / stage / 'micro'
                output.mkdir(parents=True)
                suite.save_json(output / f'Q1_{stage}_summary.json', dict(
                    case='Q1', stage=stage, rows_returned=1, sha256=digest))
            with self.assertRaisesRegex(RuntimeError, 'resultados cambiaron'):
                suite.validate_results(root)

    def test_summary_keeps_micro_and_load_profiles_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for profile, median in [('micro', 1.0), ('carga', 3.0)]:
                output = root / 'Q1/A' / profile
                output.mkdir(parents=True)
                suite.save_json(output / 'Q1_A_summary.json', dict(
                    case='Q1', stage='A', median_ms=median, rows_returned=1,
                    sha256='same', iterations=10))
            with contextlib.redirect_stdout(io.StringIO()):
                records = summarize(root, root / 'comparison.csv', 'micro')
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]['median_ms'], 1.0)


if __name__ == '__main__':
    unittest.main()
