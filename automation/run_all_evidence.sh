#!/usr/bin/env bash
set -euo pipefail
task_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python_bin=${EP2_PYTHON:-python3}
if [[ -z ${EP2_PYTHON:-} && -x $task_root/.venv/bin/python ]]; then
    python_bin="$task_root/.venv/bin/python"
fi
cd -- "$task_root"
exec "$python_bin" -u automation/run_all_evidence.py "$@"
