"""Recoverable cleanup, repository evidence layout, and suite locking."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = tuple(f'Q{n}' for n in range(1, 6))
TARGETS = ('evidencias', 'evidencias_carga', 'resultados_comparativos.csv')


@contextmanager
def suite_lock(root: Path = ROOT):
    with (root / '.ep2-evidence.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Ya hay un maestro, limpieza u organización en curso') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def clean_evidence(root: Path = ROOT, dry_run: bool = False) -> Path | None:
    targets = [root / name for name in TARGETS if (root / name).exists() or (root / name).is_symlink()]
    for path in targets:
        if path.is_symlink() or path.resolve().parent != root.resolve():
            raise RuntimeError(f'Se rechaza limpiar una ruta enlazada o fuera del proyecto: {path}')
    if dry_run:
        for path in targets:
            print(f'Se movería a evidencias_respaldos/: {path}')
        return None
    backup = None
    if targets:
        backup_root = root / 'evidencias_respaldos'
        if backup_root.is_symlink():
            raise RuntimeError('evidencias_respaldos no puede ser un enlace simbólico')
        backup_root.mkdir(exist_ok=True)
        stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S_')
        backup = Path(tempfile.mkdtemp(prefix=stamp, dir=backup_root))
        for path in targets:
            path.rename(backup / path.name)
        print(f'Evidencias retiradas de las carpetas activas. Respaldo recuperable: {backup}')
    evidence = root / 'evidencias'
    for name in ('entorno', *CASES):
        (evidence / name).mkdir(parents=True, exist_ok=True)
    return backup


def organize_evidence(root: Path = ROOT):
    evidence = root / 'evidencias'
    if evidence.is_symlink():
        raise RuntimeError('evidencias no puede ser un enlace simbólico')
    evidence.mkdir(exist_ok=True)
    for path in list(evidence.iterdir()):
        if not path.is_file():
            continue
        case = path.name.split('_', 1)[0]
        if case in CASES:
            destination = evidence / case / path.name
        elif path.name[:2].isdigit():
            destination = evidence / 'entorno' / path.name
        else:
            continue
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():
            raise RuntimeError(f'No se sobrescribe la evidencia existente: {destination}')
        path.rename(destination)
    legacy_load = root / 'evidencias_carga'
    if legacy_load.is_dir() and not legacy_load.is_symlink():
        for path in list(legacy_load.iterdir()):
            case = path.name.split('_', 1)[0]
            if case in CASES:
                destination = evidence / case / 'carga_historica' / path.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    raise RuntimeError(f'No se sobrescribe la evidencia existente: {destination}')
                path.rename(destination)
        if not any(legacy_load.iterdir()):
            legacy_load.rmdir()
    print('Evidencias agrupadas por consulta en evidencias/Q1 ... evidencias/Q5.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('clean', 'organize'))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    with suite_lock():
        if args.action == 'clean':
            clean_evidence(dry_run=args.dry_run)
        elif args.dry_run:
            parser.error('--dry-run solo se aplica a clean')
        else:
            organize_evidence()


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError) as exc:
        raise SystemExit(f'ERROR: {exc}')
