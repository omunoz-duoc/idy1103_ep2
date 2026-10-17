#!/usr/bin/env bash
# Ejecutar con Bash desde Linux/WSL; usa las credenciales EP2_MYSQL_* existentes.
set -euo pipefail

usage() {
    cat <<'HELP'
Uso:
  bash automation/collect_os_evidence.sh --case Q1 --stage A [opciones]

Opciones:
  --case Q1..Q5       Consulta del laboratorio (obligatorio).
  --stage A|B|C       Etapa a medir (obligatorio).
  --iterations N     SELECT medidos, por defecto 10000. Mantener N entre A/B/C.
  --warmups N        Calentamientos, por defecto 2.
  --interval N       Intervalo pidstat en segundos enteros, por defecto 1.
  --pid N            PID local de MySQL; si se omite se detecta automáticamente.
  --sudo-monitor     Usar sudo solo para pidstat y lectura de contadores de I/O.
  --params ARCHIVO   Por defecto sql/00_parametros.sql.
  --output CARPETA   Carpeta NUEVA; por defecto evidencias/Qn/capturas_os/Qn_ETAPA_fecha.
  --python RUTA      Python del entorno con mysql-connector-python instalado.
  -h, --help         Mostrar esta ayuda.

El script detecta MySQL, ejecuta el lote y detiene pidstat automáticamente.
C crea su índice y restaura los índices FK al limpiarlo. A/B requieren índices originales.
Las credenciales se leen desde EP2_MYSQL_HOST/PORT/USER/DATABASE/PASSWORD.
Ejecutar en el host Linux del servidor MySQL. No ejecutar todo el script con sudo.
HELP
}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 2; }

task_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
case_id=''
stage=''
iterations=10000
warmups=2
interval=1
mysql_pid=''
params="$task_root/sql/00_parametros.sql"
output=''
python_bin=${EP2_PYTHON:-python3}
sudo_monitor=false

while (($#)); do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --sudo-monitor) sudo_monitor=true; shift ;;
        --case|--stage|--iterations|--warmups|--interval|--pid|--params|--output|--python)
            (($# >= 2)) || die "Falta valor para $1"
            option=$1
            value=$2
            case "$option" in
                --case) case_id=${value^^} ;;
                --stage) stage=${value^^} ;;
                --iterations) iterations=$value ;;
                --warmups) warmups=$value ;;
                --interval) interval=$value ;;
                --pid) mysql_pid=$value ;;
                --params) params=$value ;;
                --output) output=$value ;;
                --python) python_bin=$value ;;
            esac
            shift 2 ;;
        *) die "Opción desconocida: $1" ;;
    esac
done

[[ $case_id =~ ^Q[1-5]$ ]] || die 'Indique --case Q1, Q2, Q3, Q4 o Q5'
[[ $stage =~ ^[ABC]$ ]] || die 'Indique --stage A, B o C'
[[ $iterations =~ ^[1-9][0-9]*$ ]] || die '--iterations debe ser un entero positivo'
[[ $warmups =~ ^(0|[1-9][0-9]*)$ ]] || die '--warmups debe ser un entero >= 0'
[[ $interval =~ ^[1-9][0-9]*$ ]] || die '--interval debe ser un entero positivo'
if [[ -n $mysql_pid ]]; then
    [[ $mysql_pid =~ ^[1-9][0-9]*$ ]] || die '--pid debe ser un número, no el texto MYSQL_PID'
fi
[[ $(uname -s) == Linux ]] || die 'Este script requiere Linux o WSL con /proc'
command -v pidstat >/dev/null || die 'Instale pidstat: sudo apt install sysstat'
command -v "$python_bin" >/dev/null || die "No se encuentra Python: $python_bin"
[[ -f $params ]] || die "No existe el archivo de parámetros: $params"
[[ -v EP2_MYSQL_PASSWORD ]] || die 'Exporte EP2_MYSQL_PASSWORD en esta terminal'
case "${EP2_MYSQL_HOST:-127.0.0.1}" in
    localhost|127.0.0.1|::1) ;;
    *) die 'El host MySQL es remoto: ejecute el script en el servidor y configure su conexión local.' ;;
esac

if [[ -z $mysql_pid ]]; then
    mapfile -t candidates < <({ pgrep -x mysqld || true; pgrep -x mariadbd || true; } | sort -un)
    ((${#candidates[@]} == 1)) || die 'No hay un único proceso MySQL. Use pgrep -a -x mysqld y luego --pid NUMERO.'
    mysql_pid=${candidates[0]}
fi
[[ $mysql_pid =~ ^[1-9][0-9]*$ ]] || die '--pid debe ser un número, no el texto MYSQL_PID'
[[ -r /proc/$mysql_pid/stat ]] || die "No se puede leer el PID $mysql_pid"
IFS= read -r process_name < "/proc/$mysql_pid/comm"
[[ $process_name == mysqld || $process_name == mariadbd ]] || die "El PID $mysql_pid pertenece a $process_name"
"$python_bin" -c 'import mysql.connector' || die 'Instale automation/requirements.txt en este Python'
if $sudo_monitor; then
    command -v sudo >/dev/null || die 'sudo no está instalado'
    sudo -v || die 'No se pudo autorizar sudo para monitorear el proceso'
elif [[ ! -r /proc/$mysql_pid/io ]]; then
    printf 'AVISO: sin acceso a /proc/%s/io; use --sudo-monitor para medir bytes de disco.\n' "$mysql_pid" >&2
fi

# Validate indexes before any load: A/B must not accidentally run with C indexes.
"$python_bin" - "$stage" "$case_id" <<'PY'
import os
import sys
import mysql.connector

connection = mysql.connector.connect(
    host=os.getenv('EP2_MYSQL_HOST', '127.0.0.1'),
    port=int(os.getenv('EP2_MYSQL_PORT', '3306')),
    user=os.getenv('EP2_MYSQL_USER', 'root'),
    password=os.environ['EP2_MYSQL_PASSWORD'],
    database=os.getenv('EP2_MYSQL_DATABASE', 'ep2_lab'),
    connection_timeout=10,
)
try:
    cursor = connection.cursor()
    cursor.execute(
        "SELECT DISTINCT TABLE_NAME, INDEX_NAME FROM information_schema.statistics "
        "WHERE TABLE_SCHEMA=DATABASE()"
    )
    leftovers = [f'{table}.{index}' for table, index in cursor.fetchall() if index.startswith('idx_ep2_q')]
    if leftovers:
        sys.exit('ERROR: retire los índices experimentales antes de medir: ' + ', '.join(leftovers))
finally:
    connection.close()
PY

if [[ -z $output ]]; then
    mkdir -p "$task_root/evidencias/$case_id/capturas_os"
    output=$(mktemp -d "$task_root/evidencias/$case_id/capturas_os/${case_id}_${stage}_$(date +%Y%m%d_%H%M%S)_XXXXXX")
else
    # Refuse reuse so previous runs remain intact.
    mkdir -p -- "$(dirname -- "$output")"
    mkdir -- "$output" || die 'La carpeta de salida ya existe; elija un nombre nuevo'
fi
output=$(cd -- "$output" && pwd)
params=$(realpath -- "$params")
printf 'Consulta %s, etapa %s, PID %s, %s iteraciones\nSalida: %s\n' \
    "$case_id" "$stage" "$mysql_pid" "$iterations" "$output"

common=(--case "$case_id" --params "$params" --output "$output"
        --iterations "$iterations" --warmups "$warmups"
        --pidstat-pid "$mysql_pid" --pidstat-interval "$interval")
if $sudo_monitor; then
    common+=(--pidstat-sudo)
fi
cd -- "$task_root"
if [[ $stage == C ]]; then
    command_args=("$python_bin" automation/run_stage_c.py "${common[@]}")
else
    command_args=("$python_bin" automation/evidence_runner.py "${common[@]}"
                  --stage "$stage" --query "queries/${case_id}_${stage}.sql")
fi

# pipefail preserves a failed database run even if tee succeeds.
"${command_args[@]}" 2>&1 | tee "$output/${case_id}_${stage}_runner.log"
printf '\nListo. CPU/RAM/I/O: %s/%s_%s_os_pidstat.txt\n' "$output" "$case_id" "$stage"
printf 'Ventana, deltas y limitaciones: %s/%s_%s_os_metadata.json\n' "$output" "$case_id" "$stage"
