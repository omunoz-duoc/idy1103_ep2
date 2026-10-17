#!/usr/bin/env bash
set -euo pipefail
task_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    printf '%s\n' \
        'Uso: bash automation/clean_evidence.sh [--dry-run]' \
        'Mueve evidencias/, evidencias_carga/ y resultados_comparativos.csv a un respaldo.' \
        'Recrea evidencias/entorno y evidencias/Q1..Q5 vacíos. No modifica MySQL ni SQL.' \
        'Los respaldos se conservan en evidencias_respaldos/.'
    exit 0
fi
exec "${EP2_PYTHON:-python3}" "$task_root/automation/evidence_layout.py" clean "$@"
