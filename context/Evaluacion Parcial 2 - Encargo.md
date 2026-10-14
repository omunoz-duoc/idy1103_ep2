# Instrucciones Generales
1) Instalación del dataset (obligatorio)
	1.1. Crea una base de datos (o esquema) de trabajo, según tu motor, siguiendo el README_instalacion_EP2.txt.
	1.2. Ejecuta EP2_dataset.sql solo para tu motor.
	1.3. Verifica carga mínima (captura/evidencia):
- COUNT(*) de:
	- ep2_customers
	- ep2_orders
	- ep2_order_items
	- 
Evidencia requerida: captura o salida de consola mostrando el resultado de los conteos.

2) Selección de consultas críticas y línea base “ANTES” (obligatorio)
	2.1. Selecciona mínimo 2 consultas que presenten lentitud o alto costo (SQL) sobre el dataset (por ejemplo: joins, filtros por fecha/estado, agregaciones por ciudad/segmento, top productos, etc.).
	2.2. Para cada consulta, registra la línea base ANTES incluyendo:
	- Consulta completa
	- Tiempo de ejecución (ideal: promedio de 3 ejecuciones)
	- Plan de ejecución (según motor)
	- Observación del síntoma (ej: full scan, sort costoso, join ineficiente, etc.)
	
	Planes sugeridos por motor (referencial):
	- PostgreSQL: EXPLAIN (ANALYZE, BUFFERS)
	- MySQL 8+: EXPLAIN / EXPLAIN ANALYZE
	- Oracle: EXPLAIN PLAN + DBMS_XPLAN
	- Evidencia requerida: capturas/outputs del plan y del tiempo antes.

3) Identificación de congestión (obligatorio)
	3.1. Analiza el plan de ejecución ANTES e identifica al menos 2 causas por consulta, por ejemplo:
	- Full scan innecesario
	- Filtros poco selectivos
	- Join costoso o mal ordenado
	- Falta de índices en columnas de búsqueda/join
	- Sorting/hash excesivo
	- Estadísticas no actualizadas (si aplica)
	3.2. Explica el impacto: qué operación se vuelve el cuello de botella y por qué.

4) Implementación de optimizaciones (obligatorio)
	4.1. Para cada consulta crítica, aplica mínimo 2 optimizaciones, escogiendo entre:
	- Creación de índices (simples o compuestos)
	- Reescritura de la consulta (filtros más tempranos, reducción de columnas, cambios de join, subconsultas/CTE)
	- Actualización/recálculo de estadísticas (si aplica al motor)
	- Ajustes pertinentes al motor (solo si se justifican y se evidencia su efecto)
	4.2. Guarda tus cambios en scripts ordenados (ejemplo de estructura):
	- 01_consultas_before.sql
	- 02_explain_before.sql
	- 03_optimizaciones.sql (índices / stats)
	- 04_consultas_after.sql
	- 05_explain_after.sql
	Regla: toda optimización debe quedar scriptable y reproducible.

5) Medición “DESPUÉS” y comparación Antes vs Después (obligatorio)
	5.1. Ejecuta nuevamente las consultas optimizadas en condiciones comparables.
	5.2. Presenta una comparación obligatoria por consulta (tabla mínima):
	- Tiempo antes vs después
	- Cambio en el plan (operaciones relevantes)
	- Métrica del motor (buffers/rows/costo, según aplique)
	- % de mejora
Evidencia requerida: capturas del plan y tiempos ANTES y DESPUÉS.

6) Informe técnico grupal (estructura mínima obligatoria)
El informe debe incluir como mínimo:
- Contexto y objetivo de la EP2 (rendimiento)
- Instalación del dataset (con evidencia de verificación)
- Consulta 1: línea base, congestión, optimizaciones, resultados
- Consulta 2: línea base, congestión, optimizaciones, resultados
- Evaluación integral:
	- costo/beneficio
	- riesgos o efectos secundarios (ej: mayor costo en escrituras por índices)
	- limitaciones del entorno/motor
	- mejoras futuras (mínimo 2)