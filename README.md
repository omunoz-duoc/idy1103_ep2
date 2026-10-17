# EP2 — Diagnóstico y optimización de consultas MySQL

Este repositorio contiene un laboratorio reproducible para estudiar cinco consultas sobre un comercio ficticio. El objetivo no es demostrar que todo índice siempre mejora una consulta, sino comparar el comportamiento real antes y después de cada intervención.

Los datos son sintéticos. Las cifras representan pedidos y pagos registrados en el dataset, no ingresos reales ni comportamiento de clientes reales.

El [informe final](Informe_Final_Optimizacion_EP2.md) presenta las conclusiones de la corrida completa del 16 de octubre de 2026, con contexto de negocio, fundamentos técnicos y cifras de latencia y recursos.

## Qué encontrará aquí

| Ubicación | Contenido |
|---|---|
| [`dataset.sql`](dataset.sql) | Creación y carga de las seis tablas del laboratorio. Destruye y recrea esas tablas. |
| [`queries/`](queries/) | Versiones A y B de Q1–Q5. La etapa C ejecuta exactamente la versión B con un índice experimental. |
| [`sql/`](sql/) | Consultas de preparación, parámetros congelados, evidencia inicial e índices experimentales. |
| [`automation/`](automation/) | Runner de medición, ejecución por etapas, control seguro de índices C y consolidación de resultados. |
| [`docs/EJECUCION_COMPLETA.md`](docs/EJECUCION_COMPLETA.md) | Limpieza recuperable y maestro Q1–Q5 con cooldown, microbenchmark y carga sostenida. |
| [`docs/MONITOREO_OS.md`](docs/MONITOREO_OS.md) | Comandos Bash para ejecutar lotes SQL con captura automática de CPU, RAM e I/O mediante `pidstat`. |
| [`evidencias/`](evidencias/) | Salidas reales: planes, tiempos, resultados, checksums, contadores, índices y metadatos. |
| [`resultados_comparativos.csv`](resultados_comparativos.csv) | Resumen numérico A/B/C de las cinco consultas. |
| [`PROCESO_EVIDENCIA_ELI5.md`](PROCESO_EVIDENCIA_ELI5.md) | Procedimiento paso a paso para reproducir o completar las evidencias. |
| [`00_entorno.template.md`](00_entorno.template.md) | Plantilla pendiente para documentar hardware y condiciones manuales. |

## Las tres etapas

- **A — línea base:** consulta original e índices originales.
- **B — reescritura:** SQL equivalente, todavía con los índices originales.
- **C — índice:** exactamente el SQL de B con un único índice experimental para esa consulta.

Esta separación permite atribuir A→B a la reescritura y B→C al índice. Los índices C se crean de uno en uno y se eliminan después de medir para no contaminar las otras consultas.

## Ejecutar todos los casos

```bash
bash automation/run_all_evidence.sh --clean --cooldown 10 --sudo-monitor
```

Con las credenciales MySQL configuradas, el maestro respalda la corrida anterior y ejecuta Q1–Q5 sucesivamente. Cada A/B/C contiene 30 mediciones cortas y 10.000 ejecuciones de carga, con pausas de 10 segundos. La [guía completa](docs/EJECUCION_COMPLETA.md) explica opciones, permisos y evidencias adicionales.

La nueva estructura es `evidencias/Qn/A|B|C/micro|carga/`, con entorno compartido en `evidencias/entorno/`. Las tablas consolidadas quedan en `evidencias/comparacion_micro.csv` y `evidencias/comparacion_carga.csv`. `COBERTURA.md` identifica los diagnósticos faltantes y `PENDIENTES_MANUALES.md` conserva lo que requiere observación humana.

Para limpiar sin ejecutar consultas: `bash automation/clean_evidence.sh`. Los archivos se mueven a `evidencias_respaldos/`; la base de datos no se modifica.

## Guía de las consultas

La tabla siguiente y los cinco informes corresponden a la corrida histórica del 13 de octubre de 2026. Sus archivos se reagruparon en `evidencias/Qn/` sin alterar su contenido. Deben revisarse frente a los CSV de una nueva suite; el maestro conserva estos documentos y no reemplaza automáticamente sus conclusiones.

| Consulta | Pregunta de negocio | Resultado actual de la intervención completa A→C |
|---|---|---:|
| [Q1](docs/consultas/Q1.md) | ¿Cuáles son los últimos 50 pedidos `CREATED` de una sucursal? | Mediana 45,85 % menor |
| [Q2](docs/consultas/Q2.md) | ¿Cuánto se registró por pagos con tarjeta en 14 días? | Mediana 70,06 % menor |
| [Q3](docs/consultas/Q3.md) | ¿Cuáles son los 20 productos con más unidades en 14 días? | Mediana 10,24 % mayor; no se demostró mejora total |
| [Q4](docs/consultas/Q4.md) | ¿Qué clientes de un segmento tienen al menos un pedido `PAID` reciente? | Mediana 35,79 % menor |
| [Q5](docs/consultas/Q5.md) | ¿Cuál es el valor de pedidos no cancelados por sucursal de una región? | Mediana 44,05 % menor |

Los porcentajes usan la mediana del tiempo observado por el cliente Python, con 2 calentamientos y 10 ejecuciones medidas. “Menor” significa más rápido en esta corrida; no implica que el mismo porcentaje se mantenga con otro hardware, volumen o concurrencia.

## Cómo leer una evidencia

Los nombres siguen el patrón `Qn_ETAPA_tipo.ext`. Por ejemplo:

- `Q2_A_query.sql`: SQL exacto de la línea base.
- `Q2_A_tree.txt`: plan estimado.
- `Q2_A_analyze.txt`: plan ejecutado, con tiempos, filas y ciclos.
- `Q2_A_timings.csv`: las 10 observaciones de tiempo del cliente.
- `Q2_A_summary.json`: mediana, media, p95, extremos y desviación.
- `Q2_A_session_status.csv`: contadores de sesión antes/después y su delta.
- `Q2_A_indexes.csv`: índices que existían durante la medición.
- `Q2_results_A.csv`: resultado completo.
- `Q2_A_performance_schema.csv`: métrica del servidor o explicación de por qué no estuvo disponible.

Para leer una consulta:

1. Compruebe que A/B/C tienen el mismo `sha256` y cantidad de filas.
2. Compare las medianas y p95; no use solamente el mínimo.
3. Revise en `analyze.txt` cuántas filas recorrió cada operador y cuántos `loops` ejecutó.
4. Confirme en `indexes.csv` qué índice estaba activo.
5. Use los contadores como trabajo acumulado del bloque de 10 ejecuciones, no como páginas físicas ni CPU.
6. Lea la conclusión específica de Q1–Q5, donde se separa lo demostrado de lo pendiente.

## Entorno y dataset medidos

- MySQL `8.0.46-0ubuntu0.24.04.4`.
- Base `ep2_lab`, conexión local a `127.0.0.1:3306`.
- 5.000 clientes, 20.000 pedidos, 100.000 ítems, 15.000 pagos, 2.000 productos y 20 sucursales.
- Parámetros congelados: fin exclusivo `2026-10-14`, inicio corto `2026-09-30`, inicio largo `2026-07-16`, sucursal 15, método `CARD`, ciudad `Santiago`, segmento `Retail` y región `RM`.
- Estadísticas actualizadas una vez antes de la línea base.

La configuración completa está en [`00_mysql_environment.txt`](evidencias/entorno/00_mysql_environment.txt), la validación del dataset en [`01_dataset.txt`](evidencias/entorno/01_dataset.txt) y los parámetros copiados en cada evidencia `Qn_*_params.sql`.

## Qué ya está demostrado

- Los resultados A/B/C son equivalentes en las cinco consultas: cada consulta conserva filas y checksum.
- Q1 y Q2 eliminan trabajo claramente observable al usar sus índices C.
- Q4 obtiene un semijoin con `EXISTS` y luego reduce el trabajo por cliente con un índice cubriente.
- Q5 acelera la corrida con lectura cubierta, aunque no reduce las filas recorridas ni el sort final.
- Q3 mejora el acceso inicial a pedidos, pero el JOIN, la agregación temporal y el sort continúan dominando; la latencia total no mejora frente a A.

## Evidencia todavía pendiente

No debe completarse esta parte con suposiciones:

- `00_entorno.md` real con CPU, núcleos, RAM, disco, Docker/WSL y carga concurrente: **__________________**
- Capturas exigidas por la pauta, etiquetadas por consulta y etapa: **__________________**
- CPU, RAM e I/O del proceso MySQL durante lotes A/B/C equivalentes: **__________________**
- Prueba con carga sostenida o más repeticiones/intercalado para evaluar estabilidad: **__________________**
- Costo de escritura de cada índice mediante INSERT/UPDATE/DELETE controlados: **__________________**
- Tamaño individual fiable de cada índice y proyección de crecimiento: **__________________**
- Evidencia de Performance Schema: no se obtuvo porque `ep2_runner` no tenía permiso sobre `performance_schema.threads`; además `events_statements_history_long` estaba deshabilitado. Conclusión basada en esa fuente: **__________________**

La ausencia de esas mediciones no invalida los tiempos, planes y contadores ya guardados, pero limita cualquier afirmación sobre CPU, I/O físico, contención, escalabilidad o costo operacional.

La recolección individual de CPU/RAM/I/O puede ejecutarse con `bash automation/collect_os_evidence.sh --case Q1 --stage A --sudo-monitor`. Cada corrida crea una carpeta nueva en `evidencias/Q1/capturas_os/`. El [procedimiento de monitoreo](docs/MONITOREO_OS.md) explica cómo repetir A/B/C y leer sus archivos.

## Reproducibilidad y seguridad

El proceso completo está documentado en [`PROCESO_EVIDENCIA_ELI5.md`](PROCESO_EVIDENCIA_ELI5.md). Las credenciales se leen desde variables de entorno y no deben guardarse en el repositorio. `automation/run_stage_c.py` controla los índices experimentales y restaura los índices que soportan claves foráneas antes de limpiar Q1, Q4 y Q5.
