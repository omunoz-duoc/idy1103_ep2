# Limpiar y ejecutar todos los experimentos

El maestro ejecuta Q1, Q2, Q3, Q4 y Q5, en ese orden. Para cada consulta hace A, B y C; dentro de cada etapa hace un microbenchmark y un lote de carga sostenida. Espera un cooldown configurable antes de cada lote.

## 1. Preparación

Use la misma base `ep2_lab` ya cargada y los parámetros congelados de `sql/00_parametros.sql`. Configure las variables `EP2_MYSQL_HOST`, `EP2_MYSQL_PORT`, `EP2_MYSQL_USER`, `EP2_MYSQL_DATABASE` y `EP2_MYSQL_PASSWORD` como en el [procedimiento inicial](../PROCESO_EVIDENCIA_ELI5.md).

El maestro elige `.venv/bin/python` si existe; puede seleccionar otro entorno exportando `EP2_PYTHON`. Linux/WSL necesita `pidstat` (`sudo apt install sysstat`). El proceso MySQL debe estar en el mismo host y corresponder a la conexión SQL.

## 2. Ver qué se ejecutará

```bash
bash automation/run_all_evidence.sh --dry-run
bash automation/clean_evidence.sh --dry-run
```

El dry-run del maestro no conecta a MySQL, no carga consultas y no mueve archivos.

## 3. Ejecutar la suite completa

```bash
bash automation/run_all_evidence.sh \
  --clean \
  --cooldown 10 \
  --iterations 30 \
  --load-iterations 10000 \
  --sudo-monitor
```

Esto genera **15 microbenchmarks y 15 lotes de carga**. La carga hace 10.000 SELECT por etapa, con un cliente secuencial. Q3 puede tardar varios minutos por etapa. Use el mismo número de iteraciones y la misma configuración en A/B/C.

`--clean` mueve primero las evidencias anteriores a `evidencias_respaldos/FECHA_ID/`; así comienza una corrida completa sin mezclar resultados. La conexión y los índices residuales se validan antes de retirar archivos. Si la carpeta activa ya contiene archivos y no usa `--clean`, el maestro se detiene para preservar la evidencia.

El cooldown mantiene la caché de MySQL. Ayuda a separar los lotes, pero no equivale a una prueba en frío ni garantiza que desaparezca actividad ajena. Creación/limpieza de índices y captura de planes quedan fuera de la ventana CPU/I/O.

Puede omitir `--sudo-monitor` si tiene acceso a los contadores de I/O. Cuando falta ese permiso, se registra `null` y el motivo. `sudo` se usa únicamente para el monitoreo del sistema operativo; SQL usa su usuario de laboratorio.

Si `sudo` solicita contraseña, ingrese la de su usuario Linux. El runner comparte la terminal del maestro, valida la autorización antes del lote y la renueva sin interacción cada 30 segundos mientras captura. La contraseña no se guarda ni se transmite al runner. Si cancela la autorización, la medición se detiene con un mensaje explícito.

Para una ejecución ligera que solo mida SQL y planes:

```bash
bash automation/run_all_evidence.sh --clean --skip-load --cooldown 5
```

Si hay más de una instancia MySQL, indique `--pid NUMERO`. `--analyze-initial` permite ejecutar `ANALYZE TABLE` una sola vez antes de A si el usuario tiene los permisos necesarios. Sin esa opción, se conservan las estadísticas existentes y su estado queda registrado.

## 4. Limpieza independiente y recuperación

```bash
bash automation/clean_evidence.sh
```

La limpieza mueve únicamente `evidencias/`, la antigua `evidencias_carga/` y `resultados_comparativos.csv`, si existen. Después crea `evidencias/entorno/` y `evidencias/Q1/` hasta `Q5/` vacías. No modifica datos, índices, consultas, parámetros, documentación ni la ficha manual del entorno.

Para recuperar una corrida, localice el respaldo indicado por el script. Primero retire la corrida activa con el mismo limpiador, y luego mueva la carpeta `evidencias` del respaldo elegido a la raíz del proyecto. No fusione carpetas de dos corridas; sus métricas y parámetros podrían pertenecer a condiciones distintas.

La limpieza de archivos no elimina índices residuales de una ejecución que haya sido terminada abruptamente. El maestro informa el nombre si encuentra alguno. Repárelo con `python automation/run_stage_c.py --case Qn --cleanup-only`, reemplazando Qn por el caso indicado.

## 5. Estructura de salida

```text
evidencias/
  ejecucion.json                 # configuración, fechas y estado complete/failed/interrupted
  maestro.log                    # secuencia real y pausas
  comparacion_micro.csv          # A/B/C, latencia con 30 ejecuciones
  comparacion_carga.csv          # A/B/C, latencia + CPU/RAM/I/O del lote sostenido
  COBERTURA.md                   # métricas no disponibles, permisos y lotes demasiado cortos
  PENDIENTES_MANUALES.md          # capturas y argumentación por completar
  integridad_sha256.csv          # hash de los archivos generados
  entorno/
    00_parametros.sql
    mysql_*.csv                  # versión, configuración, instrumentos, DDL, distribuciones
    host_*.txt                   # CPU, RAM, discos, kernel, proceso
    dataset_before.json          # conteos exactos y hash de todas las filas por tabla
    dataset_after.json
    dataset_equivalence.json
    fuentes_sha256.json          # versiones del dataset, consultas y automatización
  Q1/
    README.md                   # índice automático de resultados de esta corrida
    equivalencia.json            # igualdad entre A/B/C y entre micro/carga
    A/
      micro/                    # planes, tiempos, resultados, contadores
      carga/                    # lo anterior + muestras CPU/RAM/I/O
    B/
      micro/
      carga/
    C/
      ddl.json                  # tiempo CREATE, limpieza y restauración del índice FK
      indices_before.csv
      indices_with_experiment.csv
      indices_after_cleanup.csv
      before_index_pages.csv    # si hay permisos sobre mysql.innodb_index_stats
      with_experiment_index_pages.csv
      micro/
      carga/
  Q2/ ... Q5/                   # la misma estructura por consulta
```

Las evidencias anteriores a esta suite se reagruparon en `evidencias/Qn/` directamente, y sus antiguos lotes OS en `Qn/carga_historica/`. La nueva ejecución con `--clean` conserva todo eso dentro del respaldo. Las conclusiones actuales de `docs/consultas/Qn.md` corresponden a esa corrida histórica y deben revisarse con los nuevos resultados.

## 6. Evidencias adicionales y sus límites

| Evidencia | Para qué sirve | Límite |
|---|---|---|
| TREE, ANALYZE, EXPLAIN tradicional y JSON | Comparar accesos, cobertura, operadores, filas y estimaciones | Los costos estimados no son milisegundos; ANALYZE se mide fuera del benchmark |
| SHA-256 del resultado y CSV completo | Validar equivalencia de A/B/C | Hash normalizado sin dependencia del orden; el CSV conserva el orden de salida |
| Hash de todas las filas del dataset antes/después | Detectar cambios de datos durante la suite | No sustituye aislar el servidor ante escrituras concurrentes transitorias |
| Deltas de sesión | Trabajo lógico: handlers, scans, sorts y temporales | Son acumulados del bloque, no páginas físicas |
| Contadores globales InnoDB antes/después | Lecturas del buffer pool, disco, log y esperas | Incluyen otras sesiones y diagnóstico; no son exclusivos de la consulta |
| I/O por índice en Performance Schema | Identificar qué índices reciben lecturas y escrituras | Acumulados del esquema; revisar snapshots y concurrencia |
| Historial de sentencias | Tiempo del servidor, filas examinadas/enviadas, sort y temporales | Depende de permisos e instrumentos; se intenta history_long y luego history |
| Esperas de locks y estado de conexiones | Contextualizar contención y actividad simultánea | Dos snapshots no detectan todas las esperas breves; conexiones visibles dependen de permisos |
| Páginas estadísticas del índice | Aproximar costo de espacio individual | Puede estar desactualizado; no confundir INDEX_LENGTH de la tabla con tamaño exacto del índice |
| Tiempo de CREATE y limpieza | Cuantificar costo de desplegar/retirar el índice | Incluye red y trabajo asociado del servidor |
| pidstat CPU/RSS/I/O/cambios de contexto | Medir recursos del proceso durante carga sostenida | Incluye todas las sesiones, cachés y muestras parciales de borde |

Los intentos de diagnóstico que fallan quedan documentados en `*_availability.json`; Performance Schema tiene su propio `*.status.json`. El maestro no cambia permisos ni habilita consumidores automáticamente. Consulte [04_permisos_observabilidad.example.sql](../sql/04_permisos_observabilidad.example.sql) si el administrador desea habilitar lecturas adicionales antes de toda la suite.

Las comparaciones de carga incluyen CPU por consulta y consultas/segundo. Compare el mismo número de operaciones: un %CPU menor durante más tiempo puede consumir más CPU total.

## 7. Fallos y trabajo pendiente

Si un lote falla, cambia el resultado o cambia el dataset, la suite se detiene y deja `ejecucion.json` con el fallo y un manifiesto de los archivos recogidos. Si C había creado un índice, intenta restaurar los índices FK y retirarlo. El inventario original se verifica después de cada limpieza. `Ctrl+C` y SIGTERM solicitan cierre; SIGKILL o un corte de energía pueden requerir recuperación manual.

Todavía debe registrar concurrencia y condiciones reales, tomar las capturas exigidas y completar las conclusiones del negocio. El costo de INSERT/UPDATE/DELETE requiere otro experimento sobre una copia de laboratorio; la suite no inventa ese costo ni altera los datos para medirlo.
