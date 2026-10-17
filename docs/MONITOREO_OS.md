# Evidencias de CPU, RAM e I/O durante las consultas

`MYSQL_PID` en un comando de ejemplo significa «reemplace esto por el número del proceso MySQL». Si se deja el texto literal, `pidstat` muestra su ayuda. El script Bash detecta ese número y coordina el monitoreo con el lote SQL.

Para recopilar todas las evidencias Q1–Q5 en una sola ejecución con cooldown y limpieza recuperable, use el [script maestro](EJECUCION_COMPLETA.md). Este documento describe capturas individuales.

## 1. Preparar el entorno

Use Linux o WSL en el equipo donde se ejecuta MySQL. Active el entorno Python que utilizó para las mediciones anteriores e instale `pidstat` si falta:

```bash
sudo apt install sysstat
source .venv/bin/activate
```

Use sus valores de conexión habituales. En una terminal nueva:

```bash
export EP2_MYSQL_HOST=127.0.0.1
export EP2_MYSQL_PORT=3306
export EP2_MYSQL_USER=ep2_runner
export EP2_MYSQL_DATABASE=ep2_lab
read -s -p "Contraseña MySQL: " EP2_MYSQL_PASSWORD
export EP2_MYSQL_PASSWORD
echo
```

La contraseña de MySQL es distinta de la contraseña que `sudo` puede solicitar para acceder a contadores del sistema operativo.

Para `sudo`, escriba la contraseña de su usuario Linux. La autorización se valida antes del lote y se renueva cada 30 segundos mientras monitorea. Use una terminal interactiva; las contraseñas no se guardan en las evidencias.

## 2. Medir Q1 en A, B y C

Ejecute estos comandos uno después del otro desde la raíz del proyecto:

```bash
bash automation/collect_os_evidence.sh --case Q1 --stage A --sudo-monitor
bash automation/collect_os_evidence.sh --case Q1 --stage B --sudo-monitor
bash automation/collect_os_evidence.sh --case Q1 --stage C --sudo-monitor
```

Cada comando:

1. Detecta el proceso `mysqld` y valida la conexión y ausencia de índices experimentales previos.
2. Crea una carpeta nueva bajo `evidencias/Q1/capturas_os/` (o la consulta indicada).
3. Prepara los planes y ejecuta los dos calentamientos.
4. Inicia `pidstat` y ejecuta **10.000 SELECT medidos**, en una misma conexión, con CPU/RAM/I/O muestreados cada segundo.
5. Guarda tiempos, resultados, contadores SQL y evidencia del sistema operativo; detiene `pidstat` al terminar.

Para C también crea el índice de Q1 antes de medir y lo elimina al terminar, restaurando el índice de soporte FK si hace falta. El monitoreo excluye creación/limpieza del índice, `EXPLAIN ANALYZE` y calentamientos. La ventana incluye el lote de consultas, transferencia de resultados, cálculo de checksums entre iteraciones y snapshots de sesión.

`--sudo-monitor` solicita autorización para ejecutar únicamente `pidstat` y leer `/proc/PID/io` con permisos elevados. Ejecute el script como su usuario habitual. Puede omitir esta opción si su usuario ya tiene permisos sobre esos contadores. Si no los tiene, la captura de CPU/RAM sigue disponible y el JSON marca el I/O como `null`, con la causa en `io_error`.

## 3. Repetir para Q2–Q5

Cambie `--case Q1` por `Q2`, `Q3`, `Q4` o `Q5`. Para ejecutar los quince lotes secuencialmente:

```bash
for consulta in Q1 Q2 Q3 Q4 Q5; do
  for etapa in A B C; do
    bash automation/collect_os_evidence.sh \
      --case "$consulta" --stage "$etapa" --sudo-monitor || break 2
  done
done
```

Estas son mediciones de carga sostenida adicionales. Las evidencias anteriores se conservan dentro de la carpeta de cada consulta. Si el servidor es rápido, el script avisa cuando el lote dura menos de cinco intervalos de muestreo. En ese caso aumente las iteraciones **para las tres etapas**:

```bash
bash automation/collect_os_evidence.sh --case Q1 --stage A --iterations 50000 --sudo-monitor
bash automation/collect_os_evidence.sh --case Q1 --stage B --iterations 50000 --sudo-monitor
bash automation/collect_os_evidence.sh --case Q1 --stage C --iterations 50000 --sudo-monitor
```

Mantenga parámetros, número de ejecuciones, calentamientos, intervalo y concurrencia iguales entre A/B/C. Q3 puede tardar varios minutos con 10.000 ejecuciones.

## 4. Dónde están los resultados

El script imprime la carpeta exacta, por ejemplo:

```text
evidencias/Q1/capturas_os/Q1_A_20261016_153000_XXXXXX/
  Q1_A_os_pidstat.txt
  Q1_A_os_metadata.json
  Q1_A_runner.log
  Q1_A_timings.csv
  Q1_A_summary.json
  ...planes, índices, parámetros y demás evidencias SQL...
```

- `os_pidstat.txt`: muestras de `%CPU`, `RSS`, `%MEM`, fallos de página y `kB_rd/s`, `kB_wr/s` del proceso MySQL. La cabecera muestra las unidades. Con `-h`, no se agrega una fila de promedio al final.
- `os_metadata.json`: inicio/fin exactos del lote, duración, CPU acumulada del proceso en segundos, porcentaje de CPU respecto a un núcleo, RSS inicial/final en KiB y deltas de bytes de I/O. Indica si el lote fue corto, si falló y si el proceso siguió siendo el mismo.
- `runner.log`: mensajes del runner y, para C, creación y limpieza del índice.

El `pidstat` puede incluir una muestra parcial anterior al inicio y hasta un intervalo posterior al lote, para alcanzar a registrar el final. Use las marcas de inicio/fin del JSON al interpretar los bordes. Los deltas `/proc` del JSON se toman inmediatamente alrededor del lote y no incluyen esa espera final.

Para comparar, use CPU en segundos para el mismo número de operaciones, CPU por operación (`cpu_seconds / iterations`), RSS y tasas de I/O junto con duración/throughput (`iterations / batch_elapsed_seconds`). Un porcentaje de CPU menor por sí solo no demuestra menor consumo total: el lote puede haber tardado más.

## 5. Qué se puede concluir

Estos datos representan el proceso completo de MySQL durante la ventana. Si otras sesiones trabajaron al mismo tiempo, sus recursos también aparecen. RAM RSS pertenece a todo el servidor y a sus cachés; el I/O de escritura puede completarse después de la ventana. Cero bytes leídos puede reflejar caché; `null` significa que no se pudieron obtener los contadores.

Complete las conclusiones de Q1–Q5 cuando existan las nuevas capturas. Registre también hardware, concurrencia e interrupciones en `00_entorno.md`. El script prepara archivos de texto; las capturas de pantalla siguen pendientes cuando las exija la pauta.

## Opciones y problemas frecuentes

```bash
bash automation/collect_os_evidence.sh --help
```

- **Python no encuentra el conector:** active el entorno correcto o use `--python .venv/bin/python`; instale `python -m pip install -r automation/requirements.txt` en ese entorno.
- **Más de un proceso MySQL:** identifique el servidor con `pgrep -a -x mysqld` y pase `--pid 1234`, reemplazando `1234` por el PID correcto. Debe coincidir con la instancia SQL que recibe la consulta.
- **Índice experimental residual:** repare el caso con `python automation/run_stage_c.py --case Q1 --cleanup-only`, ajustando el número, antes de medir otra etapa.
- **Carpeta de salida existente:** `--output` exige una carpeta nueva para preservar corridas anteriores.
- **Servidor remoto o Docker:** este script está diseñado para MySQL nativo en el mismo host/espacio de procesos. Para Docker use el PID correcto del host y verifique puerto/contenedor; para un servidor remoto ejecute la captura en su host. No interprete las métricas de su PC cliente como métricas del servidor.
