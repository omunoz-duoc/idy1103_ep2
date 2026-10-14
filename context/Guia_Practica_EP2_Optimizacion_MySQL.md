# EP2 — Guía práctica de diagnóstico, optimización y monitoreo SQL (MySQL 8)

**Caso de negocio:** cadena de comercios con sucursales, clientes, catálogo de productos, pedidos, detalles de pedido y pagos.  
**Entregable de esta guía:** diseñar, ejecutar y documentar **cinco experimentos**, cada uno con una hipótesis y **al menos dos intervenciones comprobables**.  
**Estado:** protocolo de experimentación; **no hay mediciones reales todavía**. Los resultados y conclusiones deben completarse con los outputs de tu instancia.

> **Lectura de la pauta:** `Evaluacion Parcial 2 - Encargo.md` exige instalar/verificar la base, seleccionar **mínimo dos consultas**, medir tiempos y planes ANTES, identificar **al menos dos causas por consulta**, aplicar **mínimo dos optimizaciones por consulta**, volver a medir y presentar informe técnico con riesgos y al menos dos mejoras futuras. Aquí se proponen cinco consultas para superar el mínimo. Los materiales 2.1.1–2.4.1 exigen planes interpretados, indicadores de tiempo/filas/I/O/CPU si están disponibles, comparaciones consistentes y considerar la sobreindexación. Las propuestas de consultas, índices, instrumentación y control experimental que siguen son **diseño técnico adicional**, no resultados ya demostrados por los archivos.

## 0. Análisis previo del dataset y sus límites

### 0.1 Modelo y tamaños nominales

| Tabla | Filas previstas | Información | Índices/relaciones existentes |
|---|---:|---|---|
| `ep2_stores` | 20 | sucursal y región | PK `store_id` |
| `ep2_customers` | 5.000 | ciudad, segmento, creación | PK `customer_id` |
| `ep2_products` | 2.000 | nombre, categoría, precio | PK `product_id` |
| `ep2_orders` | 20.000 | cliente, sucursal, estado, fecha, total | PK `order_id`; FK a clientes y sucursales |
| `ep2_order_items` | 100.000 | pedido, producto, cantidad y precio unitario | PK `item_id`; FK a pedidos y productos |
| `ep2_payments` | 15.000 | pedido, fecha, medio y monto | PK `payment_id`; FK a pedidos |

**Importante:** InnoDB necesita índices para comprobar las FK y MySQL crea índices de apoyo si no existen índices aptos. Por tanto, las columnas de relación (`orders.customer_id`, `orders.store_id`, `order_items.order_id`, `order_items.product_id`, `payments.order_id`) **no deben presentarse como desindexadas** sin verificar `SHOW INDEX`. El problema a contrastar será la **combinación de filtros, fecha, orden o cobertura**, no fingir ausencia absoluta de índices en JOIN.

El esquema **no** contiene inventario, costos, devoluciones ni estados detallados de cobranza. No atribuyas conclusiones que dependan de esas entidades.

### 0.2 Limitaciones reales de la carga sintética

1. La secuencia recursiva que produce 5.000, 20.000 o 100.000 filas puede superar `cte_max_recursion_depth` (predeterminado 1.000 en MySQL). **Antes de ejecutar el archivo**, en la *misma conexión* de importación:

   ```sql
   SET SESSION cte_max_recursion_depth = 110000;
   ```

   El archivo hace `DROP TABLE`: **destruye tablas previas**. Ejecútalo en un esquema exclusivo de laboratorio. Si falla una carga intermedia, **no continúes sobre datos parciales**; corrige la configuración y ejecuta desde cero. En servicios administrados o conexiones distintas puede hacer falta configuración adicional.

2. `RAND()` cambia los datos cada vez; **carga una sola vez** y trabaja sobre esa copia. Exporta un respaldo o instantánea si necesitas repetir experimentos. Esos números son objetivos de generación, no conteos comprobados.
3. La carga asigna `status` y pagos de manera **independiente**. Un pedido `CANCELLED` puede tener pagos y un pedido `PAID` puede no tenerlos. También puede haber múltiples pagos, pagos por valor distinto al total, y pagos con fecha anterior al pedido. El `total_amount` se obtiene de ítems, pero los pedidos sin ítems conservan 0. Por eso, los reportes financieros deben decir **"pagos registrados"** o **"pedidos marcados PAID"**, sin equiparar automáticamente ambos.
4. Productos aleatorios pueden ser considerados inactivos aunque tengan ventas históricas. No filtres `is_active=1` para calcular ventas pasadas.
5. El dataset es relativamente pequeño: una consulta puede tardar milisegundos y la ganancia por índice resultar mínima o nula; **un resultado negativo es evidencia válida**. No infles artificialmente métricas ni fuerces índices en la medición principal.

## 1. Preparación, control del entorno y evidencia inicial

### 1.1 Ficha del entorno (guardar `evidencias/00_entorno.md`)

Registrar: fecha/hora, MySQL exacto (`SELECT VERSION()`), Windows/WSL/Linux o Docker, versión del cliente (Workbench/DBeaver/CLI), CPU y núcleos, RAM, disco SSD/HDD, memoria asignada a MySQL/Docker/WSL, concurrencia conocida, modo de conexión, versión del dataset, y si hay cargas externas. Captura de pantalla opcional adicional, pero **guardar salidas de texto** siempre.

```sql
CREATE DATABASE IF NOT EXISTS ep2_lab CHARACTER SET utf8mb4;
USE ep2_lab;
SELECT VERSION() AS version_mysql, @@version_comment AS distribucion;
SHOW VARIABLES WHERE Variable_name IN (
 'performance_schema','innodb_buffer_pool_size','cte_max_recursion_depth',
 'max_connections','optimizer_switch','slow_query_log','long_query_time'
);
SHOW GLOBAL STATUS WHERE Variable_name IN ('Threads_connected','Threads_running');
```

> El archivo provisto **no trae el README de instalación aludido en la pauta**. Esta guía proporciona una instalación equivalente para MySQL, pero registra esa ausencia en el informe en vez de atribuirle contenido inexistente.

**Importación (cliente `mysql`, ejemplo):** primero entrar al cliente con `mysql -u TU_USUARIO -p ep2_lab`, ejecutar `SET SESSION cte_max_recursion_depth = 110000;` y en esa **misma sesión** ejecutar `SOURCE /ruta/EP2_dataset\ -\ mysql.sql;` (alternativamente copiar/pegar la ruta apropiada según cliente o ejecutar el archivo mediante la función *Run SQL Script* si puedes establecer antes el parámetro en esa misma conexión). Las rutas con espacios pueden ser problemáticas con `SOURCE`; es más fácil copiar el archivo al laboratorio como `dataset.sql` y ejecutar `SOURCE /ruta/dataset.sql;`. **No** pegar contraseñas en los entregables.

### 1.2 Verificación y perfilado (guardar `evidencias/01_dataset.txt`)

```sql
USE ep2_lab;
SELECT 'customers' AS tabla, COUNT(*) AS filas FROM ep2_customers
UNION ALL SELECT 'orders', COUNT(*) FROM ep2_orders
UNION ALL SELECT 'order_items', COUNT(*) FROM ep2_order_items
UNION ALL SELECT 'payments', COUNT(*) FROM ep2_payments
UNION ALL SELECT 'products', COUNT(*) FROM ep2_products
UNION ALL SELECT 'stores', COUNT(*) FROM ep2_stores;

SHOW CREATE TABLE ep2_orders;
SHOW CREATE TABLE ep2_order_items;
SHOW INDEX FROM ep2_orders;
SHOW INDEX FROM ep2_order_items;
SHOW INDEX FROM ep2_payments;
SHOW INDEX FROM ep2_customers;
SHOW INDEX FROM ep2_products;
SHOW INDEX FROM ep2_stores;

SELECT MIN(order_ts) AS primera_orden, MAX(order_ts) AS ultima_orden,
       COUNT(DISTINCT customer_id) AS clientes_con_pedidos FROM ep2_orders;
SELECT status, COUNT(*) AS n FROM ep2_orders GROUP BY status;
SELECT method, COUNT(*) AS n FROM ep2_payments GROUP BY method;
SELECT category, COUNT(*) AS n FROM ep2_products GROUP BY category;
SELECT city, segment, COUNT(*) AS n FROM ep2_customers GROUP BY city, segment;
SELECT COUNT(*) AS pedidos_sin_items FROM ep2_orders o
WHERE NOT EXISTS (SELECT 1 FROM ep2_order_items i WHERE i.order_id=o.order_id);
SELECT COUNT(*) AS pedidos_pagados_sin_pago FROM ep2_orders o
WHERE o.status='PAID' AND NOT EXISTS
 (SELECT 1 FROM ep2_payments p WHERE p.order_id=o.order_id);
SELECT COUNT(*) AS pagos_de_pedidos_cancelados FROM ep2_payments p
JOIN ep2_orders o ON o.order_id=p.order_id WHERE o.status='CANCELLED';
```

**Validación obligatoria:** confirmar especialmente `customers=5000`, `orders=20000`, `order_items=100000` (si no coincide, diagnosticar). Guardar también la distribución y los índices existentes. `ANALYZE TABLE` solo **una vez antes de tomar la línea base** para uniformar estadísticas; no presentarlo después como mejora aislada a menos que lo midas como intervención específica.

```sql
ANALYZE TABLE ep2_customers, ep2_products, ep2_stores,
              ep2_orders, ep2_order_items, ep2_payments;
```

### 1.3 Congelar parámetros temporales

La carga usa `NOW()`; para evitar comparar ventanas que se desplazan, toma una fecha máxima **fija** de la copia. En cada sesión de ejecución de pruebas:

```sql
SET @end_ts   := (SELECT DATE(MAX(order_ts)) + INTERVAL 1 DAY FROM ep2_orders);
SET @start_ts := @end_ts - INTERVAL 14 DAY;
SET @long_start_ts := @end_ts - INTERVAL 90 DAY;
SELECT @start_ts AS inicio_14d, @long_start_ts AS inicio_90d, @end_ts AS fin_exclusivo;
```

**Registrar sus valores literales en `00_parametros.sql` y usar esos mismos valores en todas las sesiones** (por ejemplo `SET @start_ts='AAAA-MM-DD 00:00:00'; ...`). La fecha final es exclusiva: `[inicio, fin)`. Mantener fijos además `@store_id`, `@region`, `@city`, `@segment`, `@category`, `@method` según sección siguiente. Para medición con herramientas que abren una conexión por consulta, **sustituye variables por literales equivalentes**; de otro modo pierdes las variables de sesión.

### 1.4 Protocolo estándar para las cinco consultas

Cada caso tendrá las mismas etapas:

| Etapa | Qué se ejecuta | Objetivo |
|---|---|---|
| **A — baseline** | SQL original sin índice experimental | Confirmar problema y cuantificarlo |
| **B — intervención 1** | Reescritura del SQL, sin índice experimental | Aislar beneficio de SQL sargable, menor trabajo o semántica equivalente |
| **C — intervención 2** | Exactamente el SQL de B + índice nuevo | Aislar beneficio incremental del índice |

**No ejecutar todos los casos de forma acumulativa sin control:** los índices de un caso pueden mejorar otro y contaminar la línea base. Opciones válidas: (preferida) respaldar y restaurar el mismo esquema por caso; (simple) correr **todas las etapas A de Q1–Q5 primero**, luego B, y finalmente instalar el índice **solo del caso** que estés midiendo, guardar C y quitarlo antes de probar el siguiente caso. Mantener únicamente índices FK/PK de origen. Ejecutar `SHOW INDEX` antes de cada A/C y comprobar que no hay índices residuales. El índice creado en C no debe existir en A/B. Nunca eliminar índices asociados a FK.

En **cada etapa**:

1. Confirmar conteos, parámetros, índices activos y ausencia de carga concurrente importante.
2. Ejecutar `EXPLAIN FORMAT=TREE <consulta>;` y guardar la salida como `Qn_A_tree.txt` (o B/C). `TREE` requiere una versión MySQL compatible.
3. Ejecutar `EXPLAIN ANALYZE <consulta>;` **una vez fuera del conjunto de tiempos**. Guarda `Qn_A_analyze.txt`; analiza *actual time, actual rows, loops* y operadores. **`EXPLAIN ANALYZE` ejecuta el SELECT**: no es un tiempo independiente comparable con la ejecución normal. En versiones MySQL 8 más recientes se admite formato `TREE` explícito; no usar `FORMAT=JSON` con `EXPLAIN ANALYZE` sin verificar compatibilidad.
4. Hacer **2 calentamientos** con el SELECT real, fuera del conjunto medido (no reiniciar MySQL entre A/B/C).
5. Ejecutar la misma sentencia **10 veces** en cliente con salida suprimida/medida por un mismo runner. Guardar los **10 tiempos en ms**, mediana, media, mínimo, máximo, p95 (con 10 datos, interpolación o rango superior; documentar método), desviación estándar. Para cumplir literalmente la pauta bastan 3, pero 10 dan mejor contexto si los tiempos son muy pequeños. Si el motor responde en menos de 1 ms, ejecutar lotes de muchas consultas individuales, dividir por repeticiones e informarlo explícitamente.
6. Medir counters/Performance Schema y CPU/IO de SO en ventana definida; registrar si la resolución permite atribuir cambios (ver §3). Tomar snapshots antes y después; **no interpretar un contador global como exclusivo de la consulta**.
7. Verificar **igualdad de resultados A, B, C**: guardar un archivo CSV ordenado de resultado completo (o un digest determinista calculado fuera de MySQL sobre todas las filas y columnas, con tipos/orden normalizados). La igualdad del `COUNT(*)` no basta si cambian las sumas. Las consultas Q1–Q5 deben preservar su semántica entre versiones.
8. Registrar hallazgo y causalidad **sin presuponer mejora**. Para Qn, el beneficio A→B es de reescritura; B→C es del índice. A→C es el efecto total.

**Regla importante:** registrar dos **causas observables** por consulta, no dos frases especulativas. Si un supuesto cuello de botella no se confirma en el plan, escribir “hipótesis no confirmada”, explicar por qué y mantener evidencia. La creación del índice y la reescritura cuentan como dos intervenciones, aunque solo una aporte ganancias.

## 2. Cinco consultas de negocio y experimentos

### Q1 — Bandeja operativa: últimos pedidos pendientes de una sucursal

**Uso real:** personal de la sucursal consulta pedidos `CREATED` recientes para prepararlos. **Problema focal:** filtrado y orden descendente (`ORDER BY ... LIMIT`) con solo índice FK en `store_id`; además `DATE()` sobre columna dificulta búsqueda por rango. **Tipo candidato:** B-tree **compuesto con orden** `(store_id, status, order_ts DESC, order_id DESC)`.

**Fijar** `@store_id` a una sucursal que tenga pedidos `CREATED` en los últimos 90 días; usa el resultado de:

```sql
SELECT store_id, COUNT(*) AS n FROM ep2_orders
WHERE status='CREATED' GROUP BY store_id ORDER BY n DESC LIMIT 5;
-- Elegir un store_id real, fijarlo en 00_parametros.sql.
```

**A — consulta original (reporte de operaciones):**

```sql
SELECT o.order_id, o.customer_id, o.order_ts, o.total_amount
FROM ep2_orders o
WHERE o.store_id=@store_id AND o.status='CREATED'
  AND DATE(o.order_ts)>=DATE(@long_start_ts)
  AND DATE(o.order_ts)<DATE(@end_ts)
ORDER BY o.order_ts DESC, o.order_id DESC
LIMIT 50;
```

**Hipótesis H1:** `DATE(o.order_ts)` impide aprovechar eficientemente un índice por rango de fecha; con la FK sobre sucursal aún podrían filtrarse y ordenarse muchas filas. Buscar en plan: `Filter`, `Sort`, filas leídas, `Limit`, presencia/ausencia de `filesort`.

**B — reescritura equivalente** (función removida; índices del origen únicamente):

```sql
SELECT o.order_id, o.customer_id, o.order_ts, o.total_amount
FROM ep2_orders o
WHERE o.store_id=@store_id AND o.status='CREATED'
  AND o.order_ts>=@long_start_ts AND o.order_ts<@end_ts
ORDER BY o.order_ts DESC, o.order_id DESC
LIMIT 50;
```

**C — mismo SELECT B y creación del índice:**

```sql
CREATE INDEX idx_ep2_q1_store_status_ts
ON ep2_orders(store_id, status, order_ts DESC, order_id DESC);
-- Repetir B sin cambios.
```

**H2:** con igualdad sobre `store_id`/`status`, el índice ordenado puede reducir recorrido y eliminar ordenamiento explícito, particularmente con `LIMIT`. **Métricas críticas:** `actual rows/loops`, sort, latencia p50/p95, lecturas lógicas. **Posible limitación:** un `LIMIT 50` pequeño y 20.000 pedidos puede dar mejora modesta. **Rollback:** `DROP INDEX idx_ep2_q1_store_status_ts ON ep2_orders;`.

### Q2 — Conciliación: montos registrados por método de pago en 14 días

**Uso real:** tesorería compara recaudación por medio de pago y cantidad de transacciones en una ventana. **Problema focal:** filtro por fecha no sargable y lectura de `amount`; **índice candidato covering/rango** `(method, paid_ts, amount)` (B-tree). Se elige **un método** para permitir un rango selectivo; evita la falsa conclusión de que `method` solo, con 3 valores, sería necesariamente selectivo.

**Fijar** `@method` a `'CARD'` (si está presente; verificar distribución). Para este caso `@start_ts/@end_ts` se calculan también desde pedidos y cubren un lapso de días cercano a los pagos, que fueron generados con `NOW()` en la misma importación; verificar no vacío.

**A:**

```sql
SELECT p.method, COUNT(*) AS operaciones,
       SUM(p.amount) AS monto_total, AVG(p.amount) AS ticket_medio
FROM ep2_payments p
WHERE p.method=@method
  AND DATE(p.paid_ts)>=DATE(@start_ts)
  AND DATE(p.paid_ts)<DATE(@end_ts)
GROUP BY p.method;
```

**H1:** aplicar `DATE` a `paid_ts` evita una búsqueda eficiente por rango; posiblemente se examinen muchos pagos. **No** añadir `JOIN ep2_orders` ni exigir `status='PAID'`: eso cambiaría el concepto de *pagos registrados*, dado el carácter sintético de los datos.

**B:**

```sql
SELECT p.method, COUNT(*) AS operaciones,
       SUM(p.amount) AS monto_total, AVG(p.amount) AS ticket_medio
FROM ep2_payments p
WHERE p.method=@method AND p.paid_ts>=@start_ts AND p.paid_ts<@end_ts
GROUP BY p.method;
```

**C:**

```sql
CREATE INDEX idx_ep2_q2_method_ts_amount
ON ep2_payments(method, paid_ts, amount);
-- Repetir exactamente B.
```

**H2:** usando igualdad `method` y rango `paid_ts`, `amount` disponible en la hoja del índice puede evitar lecturas adicionales para el agregado; confirmar `Covering index range scan` / `Using index`, **no asumirlo**. **Métricas:** filas examinadas, accesos cubiertos, buffers/IO, tiempos. **Limitación:** un índice amplio tiene costo de escritura; la selectividad de 14 días depende de la distribución. **Rollback:** `DROP INDEX idx_ep2_q2_method_ts_amount ON ep2_payments;`.

### Q3 — Reporte de demanda: top 20 productos vendidos en los últimos 14 días

**Uso real:** compras/marketing prioriza productos por unidades vendidas. **Problema focal:** reducción temprana del volumen antes de JOIN y agregación; **índice candidato:** `(order_ts, order_id)` en pedidos para rango cronológico. Los ítems ya tienen índice FK sobre `order_id`: verificarlo. Se mide el total de unidades asociadas a órdenes **no canceladas**; evita llamarlo facturación efectivamente cobrada.

**A:**

```sql
SELECT i.product_id, p.product_name,
       SUM(i.qty) AS unidades
FROM ep2_orders o
JOIN ep2_order_items i ON i.order_id=o.order_id
JOIN ep2_products p ON p.product_id=i.product_id
WHERE DATE(o.order_ts)>=DATE(@start_ts)
  AND DATE(o.order_ts)<DATE(@end_ts)
  AND o.status<>'CANCELLED'
GROUP BY i.product_id, p.product_name
ORDER BY unidades DESC, i.product_id ASC
LIMIT 20;
```

**H1:** función sobre `order_ts` + unión de conjuntos voluminosos puede obligar a escanear 20.000 órdenes y generar grupos/sort. Las claves de JOIN **sí** están indexadas: el cuello puede estar en el punto de entrada, el número de ítems o en la agregación.

**B — restringir el conjunto por fecha de modo sargable:**

```sql
SELECT i.product_id, p.product_name,
       SUM(i.qty) AS unidades
FROM ep2_orders o
JOIN ep2_order_items i ON i.order_id=o.order_id
JOIN ep2_products p ON p.product_id=i.product_id
WHERE o.order_ts>=@start_ts AND o.order_ts<@end_ts
  AND o.status<>'CANCELLED'
GROUP BY i.product_id, p.product_name
ORDER BY unidades DESC, i.product_id ASC
LIMIT 20;
```

**C:**

```sql
CREATE INDEX idx_ep2_q3_order_ts
ON ep2_orders(order_ts, order_id);
-- Repetir exactamente B.
```

**H2:** el rango por fecha reduce las órdenes que se conectan a `order_items` y, por tanto, registros intermedios, antes del agrupamiento. El `ORDER BY SUM(qty)` **no puede resolverse simplemente recorriendo este índice**; es esperable una operación de sort/agregación final. **Métricas:** filas de orders leídas, loops y filas de items, tablas temporales, tiempo total. **Limitación:** el PK ya es accesible desde índices secundarios de InnoDB; `order_id` puede resultar redundante como columna explícita: discutir si conviene el índice simple `(order_ts)` si el plan/espacio lo favorecen. **Rollback:** `DROP INDEX idx_ep2_q3_order_ts ON ep2_orders;`.

### Q4 — CRM: clientes de ciudad/segmento con al menos un pedido reciente PAID

**Uso real:** campaña de fidelización para clientes con actividad reciente de compra, usando estado administrativo `PAID` del pedido (no verificación de pagos). **Problema focal:** subconsulta correlacionada que cuenta todas las coincidencias frente a `EXISTS` que puede detenerse tras la primera; luego índice compuesto `(customer_id,status,order_ts)` para encontrar pedidos por cliente/estado/rango.

**Fijar** `@city='Santiago'`, `@segment='Retail'`, luego comprobar recuento. Mantener la ventana de 90 días para contar con suficientes casos.

**A:**

```sql
SELECT c.customer_id, c.full_name, c.city, c.segment
FROM ep2_customers c
WHERE c.city=@city AND c.segment=@segment
  AND (SELECT COUNT(*) FROM ep2_orders o
       WHERE o.customer_id=c.customer_id AND o.status='PAID'
         AND o.order_ts>=@long_start_ts AND o.order_ts<@end_ts)>0
ORDER BY c.customer_id;
```

**H1:** una cuenta correlacionada puede evaluar múltiples pedidos para determinar solo existencia; el filtro de ciudad/segmento carece de índice de búsqueda dedicado. El índice FK `orders.customer_id` ya existe: el problema no es JOIN sin índice sino filtrado incompleto **dentro del conjunto de pedidos por cliente**.

**B — `EXISTS` equivalente para `COUNT(*) > 0`:**

```sql
SELECT c.customer_id, c.full_name, c.city, c.segment
FROM ep2_customers c
WHERE c.city=@city AND c.segment=@segment
  AND EXISTS (SELECT 1 FROM ep2_orders o
              WHERE o.customer_id=c.customer_id AND o.status='PAID'
                AND o.order_ts>=@long_start_ts AND o.order_ts<@end_ts)
ORDER BY c.customer_id;
```

**C — un índice para el patrón de acceso de pedidos:**

```sql
CREATE INDEX idx_ep2_q4_cust_status_ts
ON ep2_orders(customer_id, status, order_ts);
-- Repetir exactamente B.
```

**H2:** el filtro de igualdad por cliente y estado más rango por fecha permite una búsqueda acotada; se reduce exploración por cliente. **Métricas:** subquery loops, rows/loop, latencia, lectura lógica. **Posible hallazgo alternativo:** para 5.000 clientes la búsqueda en `ep2_customers` puede dominar; evaluar como **investigación posterior separada**, no mezclar en la prueba principal, índice `ep2_customers(city,segment,customer_id)`. **Rollback:** `DROP INDEX idx_ep2_q4_cust_status_ts ON ep2_orders;`.

### Q5 — Reporte regional: valor de pedidos no cancelados por sucursal en 90 días

**Uso real:** gerencia regional compara desempeño de sucursales dentro de una región. **Problema focal:** filtro de región sobre tabla pequeña y fechas sobre tabla grande; necesidad de acceder a órdenes por sucursal/rango y sumar importes con cobertura. **Índice candidato compuesto/covering** `(store_id,order_ts,status,total_amount)`.

**Fijar** `@region='RM'`, si existe, u otra región de `ep2_stores` (verificar). **Métrica de negocio:** valor registrado en pedidos no cancelados, **no** ingreso bancario liquidado.

**A:**

```sql
SELECT s.store_id, s.store_name,
       COUNT(o.order_id) AS pedidos,
       COALESCE(SUM(o.total_amount),0) AS valor_pedidos
FROM ep2_stores s
LEFT JOIN ep2_orders o
  ON o.store_id=s.store_id
 AND DATE(o.order_ts)>=DATE(@long_start_ts)
 AND DATE(o.order_ts)<DATE(@end_ts)
 AND o.status<>'CANCELLED'
WHERE s.region=@region
GROUP BY s.store_id, s.store_name
ORDER BY valor_pedidos DESC, s.store_id;
```

**H1:** aplicar `DATE()` a la columna de la tabla grande puede impedir un rango eficiente; la agregación trae datos de varias tablas y ordena un resultado agrupado. **Cuidado:** los filtros de órdenes se quedan en `ON`, no en `WHERE`, para conservar sucursales sin actividad (resultado cero).

**B:**

```sql
SELECT s.store_id, s.store_name,
       COUNT(o.order_id) AS pedidos,
       COALESCE(SUM(o.total_amount),0) AS valor_pedidos
FROM ep2_stores s
LEFT JOIN ep2_orders o
  ON o.store_id=s.store_id
 AND o.order_ts>=@long_start_ts AND o.order_ts<@end_ts
 AND o.status<>'CANCELLED'
WHERE s.region=@region
GROUP BY s.store_id, s.store_name
ORDER BY valor_pedidos DESC, s.store_id;
```

**C:**

```sql
CREATE INDEX idx_ep2_q5_store_ts_status_total
ON ep2_orders(store_id, order_ts, status, total_amount);
-- Repetir exactamente B.
```

**H2:** `store_id` por igualdad y `order_ts` por rango pueden reducir los pedidos leídos; `status` y `total_amount` presentes en el índice pueden permitir lectura cubierta. `status` **después del rango** no necesariamente se aprovecha para acotar el recorrido; puede evaluarse como filtro de índice. El `ORDER BY SUM(...)` todavía requiere ordenamiento del resultado agregado. **Métricas:** join loops, acceso cubierto, filas, ordenamiento/temporales, latencia. **Limitación:** región tiene como mucho 20 sucursales en el dataset; **no** esperes gran mejora del sort final ni prometas grandes reducciones de CPU. **Rollback:** `DROP INDEX idx_ep2_q5_store_ts_status_total ON ep2_orders;`.

### Matriz de hipótesis a contrastar

| ID | Acción de negocio | Síntoma candidato principal | Técnica B | Técnica C | Comprobación clave |
|---|---|---|---|---|---|
| Q1 | Bandeja de pedidos | Sort + selección por sucursal/estado | `DATE()` → rango | B-tree compuesto que apoya `ORDER BY LIMIT` | Sort y filas examinadas |
| Q2 | Conciliación de pagos | Scan + agregación de montos | `DATE()` → rango | Índice compuesto **covering** | Rango/covering y lecturas |
| Q3 | Top productos | Muchos registros antes de GROUP BY | Filtro sargable de pedidos | B-tree por fecha | Rows/loops en JOIN, temporales |
| Q4 | Clientes activos | Conteo correlacionado innecesario | `COUNT>0` → `EXISTS` | B-tree cliente/estado/fecha | Loops y filas por cliente |
| Q5 | Reporte regional | Join+agregación con filtro no sargable | Filtro de fecha en `ON` sargable | Índice compuesto para JOIN+rango+cobertura | Acceso a órdenes y cobertura |

> **Diversidad de índices:** todos los índices convencionales nuevos aquí son variantes **B-tree** porque el dataset está en **InnoDB**, donde Hash no es un índice de usuario normal para estas tablas y Full-Text no corresponde a estas necesidades. Lo interesante es diferenciar el **diseño de uso**: rango, compuesto para sort, covering, búsqueda por múltiples igualdades, y JOIN/agregación. **No usar Full-Text, Hash o índices funcionales solo para aparentar diversidad** si cambian la semántica o no aportan al negocio. Un índice funcional para `DATE(order_ts)` podría ser un experimento adicional, no una sustitución automática de un filtro por rango más flexible.

## 3. Monitoreo: qué recopilar y qué significa

### 3.1 Tres capas de evidencia

| Capa | Indicador | Cómo obtenerlo | Interpretación / limitaciones |
|---|---|---|---|
| **SQL** | p50, media, p95, min/max de duración | runner repetible ejecutando SELECT normal | Mide latencia de la consulta en condiciones dadas |
| **Plan** | estimación, tiempo real, filas, loops, scan, sort | `EXPLAIN FORMAT=TREE`, `EXPLAIN ANALYZE` | Identifica operadores costosos; analyze tiene instrumentación propia |
| **MySQL** | `ROWS_EXAMINED`, `ROWS_SENT`, `SORT_ROWS`, temporales, `SELECT_SCAN` | `performance_schema.events_statements_*`, o `SHOW SESSION STATUS` delta | Mide trabajo lógico; no es equivalente directo a páginas físicas |
| **MySQL/InnoDB** | `Innodb_buffer_pool_read_requests`, `Innodb_buffer_pool_reads` | `SHOW GLOBAL STATUS` antes/después | Lecturas lógicas vs lecturas desde almacenamiento; **global**, contamina otra carga |
| **SO** | CPU del proceso `mysqld`, memoria RSS, IO de proceso | `pidstat`, `top` o PerfMon Windows | Valores muestreados, no CPU exacta atribuible a una sentencia breve |
| **Contención** | esperas/bloqueos, threads, locks | `performance_schema` / `sys` (si está habilitado) | Solo diagnosticar si hay concurrencia real |
| **Costo** | espacio de índices, tiempo de escritura | `information_schema.tables`, benchmark separado de INSERT/UPDATE | Trade-off del índice frente a mejoras en lecturas |

**`EXPLAIN` cost no son milisegundos**; compara unidades homogéneas y no calcules porcentajes de ahorro en tiempo usando costos estimados. **Filas examinadas no son páginas leídas**. **%CPU del servidor no equivale a CPU consumida por la consulta**.

### 3.2 Instrumentación de Performance Schema

Comprobar habilitación (puede requerir reinicio/configuración del servidor; no cambiarlo sin documentar):

```sql
SHOW VARIABLES LIKE 'performance_schema';
SELECT NAME, ENABLED
FROM performance_schema.setup_consumers
WHERE NAME IN ('events_statements_current', 'events_statements_history',
               'events_statements_history_long', 'events_waits_current');
```

**Si tienes permisos**, activar solo los consumidores pertinentes ANTES de medir, nunca entre A/B/C:

```sql
UPDATE performance_schema.setup_consumers SET ENABLED='YES'
WHERE NAME IN ('events_statements_current', 'events_statements_history',
               'events_statements_history_long');
UPDATE performance_schema.setup_instruments SET ENABLED='YES', TIMED='YES'
WHERE NAME LIKE 'statement/sql/%';
```

Estas modificaciones afectan la observabilidad y pueden tener overhead. Anotar si `history_long` existe, se llena y si las sentencias aparecen; el historial es de capacidad finita y puede sobrescribirse. **No asumir que tienes permiso de actualización.**

En la **misma sesión** de ejecución:

```sql
SELECT CONNECTION_ID() AS mysql_connection_id;
SELECT THREAD_ID INTO @ps_thread_id
FROM performance_schema.threads
WHERE PROCESSLIST_ID=CONNECTION_ID();

-- Tras ejecutar UNA consulta, inspeccionar sus eventos recientes:
SELECT EVENT_ID, SQL_TEXT,
       ROUND(TIMER_WAIT/1e9,3) AS elapsed_ms,
       ROUND(LOCK_TIME/1e9,3) AS lock_ms,
       ROWS_EXAMINED, ROWS_SENT, CREATED_TMP_TABLES,
       CREATED_TMP_DISK_TABLES, SORT_ROWS, SELECT_SCAN
FROM performance_schema.events_statements_history_long
WHERE THREAD_ID=@ps_thread_id
ORDER BY EVENT_ID DESC LIMIT 15;
```

`TIMER_WAIT` está en picosegundos (÷1e9 para ms). `LOCK_TIME` del evento **no equivale a todas las esperas por bloqueos de InnoDB**. Filtra registros por `SQL_TEXT`/evento que corresponda a Qn, **no confundas la propia consulta de monitoreo** con la que se mide. `SQL_TEXT` puede estar truncado; registra también timestamp/ID de corrida. Si `history_long` no está disponible, usar `events_statements_history` o deltas de sesión. **No medir `EXPLAIN ANALYZE` como si fuese el SELECT de producción**.

**Snapshots por sesión** (antes/después de cada bloque de pruebas, manteniendo misma conexión):

```sql
SHOW SESSION STATUS WHERE Variable_name IN (
 'Handler_read_key','Handler_read_next','Handler_read_rnd_next',
 'Created_tmp_tables','Created_tmp_disk_tables','Sort_rows',
 'Sort_merge_passes','Select_scan','Select_full_join'
);
```

Guardar `snapshot_before` y `snapshot_after` y restar valores por indicador. Estos son **contadores acumulados de esa conexión**: el bloque debe ejecutar únicamente las consultas de la etapa y el mínimo posible de mediciones. No confundir `Handler_read_next` con lecturas físicas.

Snapshots globales con **instancia aislada** únicamente:

```sql
SHOW GLOBAL STATUS WHERE Variable_name IN (
 'Innodb_buffer_pool_read_requests','Innodb_buffer_pool_reads',
 'Innodb_data_reads','Innodb_data_read','Threads_running',
 'Created_tmp_disk_tables'
);
```

Cuidado: `Innodb_data_read` representa bytes según versión, `Innodb_data_reads` operaciones; verificar nomenclatura exacta devuelta. Diferencias globales son **aproximaciones del sistema completo**. Si el tiempo es muy corto, los deltas de IO físico pueden ser cero por caché, lo que **no** significa que no existió trabajo lógico.

**Complemento opcional** si el esquema `sys` está disponible:

```sql
SELECT query, exec_count, total_latency, avg_latency, rows_examined,
       rows_sent, full_scan
FROM sys.statement_analysis
ORDER BY total_latency DESC LIMIT 20;
```

Es una vista **agregada** de consultas: no garantiza aislamiento de A/B/C (especialmente si el SQL tiene la misma forma o cambian índices). Úsala para contexto y frecuencia, no como único benchmark.

### 3.3 CPU, memoria e I/O del sistema operativo

**En Linux/WSL con proceso `mysqld` Linux:** instalar `sysstat` si hace falta y comprobar PID. En otra terminal, iniciar antes del lote de 10–1000 ejecuciones y detener al acabar:

```bash
pgrep -a mysqld
pidstat -u -r -d -p PID_MYSQL 1 > evidencias/Q1_A_os_pidstat.txt
# Interrumpir con Ctrl+C tras el bloque; repetir en B y C.
```

`%CPU` de `pidstat` mide uso del proceso durante intervalos y puede superar 100% en equipos multinúcleo según presentación; `RSS` memoria residente; `kB_rd/s`,`kB_wr/s` I/O de proceso. Para MySQL en **Docker**, medir dentro del contenedor si tiene herramientas o `docker stats` externamente (registra contenedor y límites). Para servidor remoto, medir **en el host real del servidor**, no tu PC cliente.

**MySQL nativo en Windows:** Monitor de recursos / Administrador de tareas para una vista general, preferiblemente **Monitor de rendimiento (`perfmon`)** con Data Collector Set a intervalos definidos y exportación CSV. Agrega `Process(mysqld*)\% Processor Time`, `Process(mysqld*)\Working Set - Private` y `Process(mysqld*)\IO Read Bytes/sec` / `IO Write Bytes/sec` si están disponibles. Comprueba el nombre real de la instancia del proceso; el contador del proceso puede acumular uso entre núcleos. Alternativa reproducible PowerShell (muestreo ligero de 1s):

```powershell
Get-Counter -Counter '\Process(mysqld*)\% Processor Time', '\Process(mysqld*)\Working Set - Private' -SampleInterval 1 -MaxSamples 30 |
  Export-Counter -Path '.\evidencias\Q1_A_cpu.blg' -FileFormat BLG
```

Ejecutar este muestreo **mientras se repite el lote**, no segundos después. Si el servicio se ejecuta bajo `mysqld` con sufijo distinto o no existe el contador, descubrir instancias con `Get-Counter -ListSet Process`. Para obtener CPU **por una sola sentencia corta** normalmente no habrá precisión suficiente; explícitamente marcarla como métrica de *carga sostenida* y no inventar atribución exacta.

**Diseño de dos tipos de ensayo:**

- **Microbenchmark aislado:** 10 o más ejecuciones independientes, secuenciales, para latencia y planes (CPU no atribuible con fiabilidad si son demasiado cortas).
- **Carga sostenida controlada:** 60–120 segundos (o número fijo de ejecuciones suficiente), con la **misma concurrencia**, el **mismo número de operaciones** y los mismos parámetros en A/B/C; muestrear CPU/RAM/IO cada 1 s. Si usas duración fija reporta **consultas/segundo**, no compares total CPU como si el número de consultas fuese idéntico. Para mayor rigor, ejecutar N consultas fijas y reportar CPU promedio durante lote y throughput. **No comparar fases con distintas cargas sin normalizar**.

### 3.4 Medición automatizada de tiempos, sin depender del GUI

Puedes usar DBeaver/Workbench para planes y capturas, pero para tiempos conviene un **runner que repita consultas en la misma conexión** y exporte CSV. Especificación mínima del runner (Python + `mysql-connector-python` o `PyMySQL`, instalado por separado):

1. Conectar una vez a `ep2_lab` por corrida, con `autocommit=True`; establecer parámetros con valores **literales congelados** en esa misma conexión.
2. Ejecutar SELECT A/B/C 2 veces para calentamiento, consumiendo **todas** las filas.
3. Para `n=10`, registrar `time.perf_counter_ns()` antes de ejecutar y después de **`fetchall()`**; las columnas reportadas por cliente pueden incluir transferencia/procesamiento, por eso mantener el mismo driver/red y dataset. Guardar `case,stage,iteration,elapsed_ms,rows_returned,checksum`.
4. Si una consulta devuelve pocas filas, aumentar `n` a 30 o ejecutar 100–1000 iteraciones; no cambiar ese valor entre etapas.
5. Para tiempo del **servidor** usa `TIMER_WAIT` de Performance Schema; para tiempo observado por el **cliente**, usar el reloj de Python. Mantener las dos métricas distinguidas.
6. Guardar checksum SHA-256 de la representación **canónica** de las filas (orden estable de consultas, tipos `Decimal` y fechas serializados consistentemente). **No** usar un hash de solo la cantidad de filas.

El SQL de Q1–Q5 es deliberadamente determinista respecto a un dataset y parámetros fijos: Q1/Q3/Q5 definen desempate en el `ORDER BY`; Q2/Q4 tienen resultados equivalentes independientemente de orden. El runner es opcional, pero los archivos de resultados por iteración y el plan son obligatorios para una justificación robusta.

### 3.5 Control de equivalencia y sensibilidad

- **Sargabilidad:** `DATE(col)>=DATE(inicio)` y `DATE(col)<DATE(fin)` equivalen a `col>=inicio AND col<fin` **aquí** porque los parámetros se fijan a medianoche y `DATETIME` no introduce zona horaria. No extrapolar sin revisión a `TIMESTAMP` ni parámetros con horas distintas.
- **Caché:** todas las fases deben calentarse con el mismo criterio. Orden de ejecución A→B→C puede favorecer posteriores por caché; si puedes, reordenar pruebas sobre snapshots clonados o ejecutar secuencias intercaladas controlando índices. Registrar limitación.
- **Planes:** una consulta puede mejorar sin cambiar plan (menor evaluación de expresión) o usar índice sin mejorar tiempo (pocas filas, acceso aleatorio); reportar ambos casos honestamente.
- **Selectividad:** si la ventana elegida devuelve cero filas, ampliar el rango de forma **idéntica** en A/B/C y dejar el motivo por escrito.
- **Índices creados en Q3 y Q5:** `order_id` de PK está implícitamente disponible en índices secundarios InnoDB; discutir redundancia y eventualmente medir una alternativa, pero conservar la intervención principal para comparación.

## 4. Procedimiento ejecutable por fases y archivos que debes guardar

### Fase 0 — Preflight

- [ ] Crear esquema `ep2_lab` exclusivo; fijar profundidad CTE en sesión de carga.
- [ ] Importar dataset solo una vez; verificar 5.000/20.000/100.000.
- [ ] Guardar inventario de índices y demás conteos/distribuciones.
- [ ] Fijar variables/literales fecha, método, región, sucursal, ciudad, segmento.
- [ ] Registrar versión/configuración, hardware, instrumentación y actividad del servidor.
- [ ] Ejecutar `ANALYZE TABLE` inicial y guardar salida.

### Fase 1 — Medición **A** de las cinco consultas, **antes de crear cualquier índice**

Para `Q1` a `Q5`: pegar consulta A exacta en `01_consultas_before.sql`; ejecutar `EXPLAIN FORMAT=TREE`; `EXPLAIN ANALYZE`; 2 warmups + 10 ejecuciones medidas; capturar métricas SQL/servidor/OS; exportar resultados completos/digest. Guardar `{Qn}_A_*`. Para cada Qn, formular: **problema de negocio → dos señales observadas → hipótesis H1 y H2**, separando causas comprobadas de sospechas.

### Fase 2 — Medición **B** (reescritura, ningún índice nuevo)

Para cada Qn: guardar SQL B en `03_optimizaciones.sql` (o archivo `rewrites/Qn_B.sql`), repetir **mismo procedimiento**. Comparar digest A vs B **antes** de aceptar el cambio. Calcular A→B. Los datos deben continuar idénticos.

### Fase 3 — Medición **C** (índice aislado)

Para cada Qn: asegurar que se retiraron índices experimentales de otros casos; crear **solo** el índice indicado para Qn (`03_optimizaciones.sql`), guardar tamaño/tiempo de creación si puede medirse; repetir `ANALYZE TABLE` **solo si resulta necesario** por estadísticas y anotarlo como posible factor adicional (idealmente aplicar el mismo criterio en todas las fases). Ejecutar **exactamente B** y recopilar C. Verificar digest y calcular B→C y A→C. Al terminar registrar DDL de rollback y eliminar ese índice antes de pasar al siguiente caso. Guardar `SHOW INDEX` como evidencia.

**Atención a `ANALYZE TABLE`:** si se ejecuta después de crear un índice, la variación puede deberse en parte a estadísticas actualizadas; deja explícito ese factor. En datasets pequeños, la creación de índice ya actualiza información y puede no ser necesario analizar otra vez.

### Fase 4 — Riesgos/costo y evaluación integral

Guardar tamaño de índices antes/después (si misma copia y sin escrituras ajenas):

```sql
SELECT TABLE_NAME, TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH
FROM information_schema.TABLES
WHERE TABLE_SCHEMA='ep2_lab'
ORDER BY TABLE_NAME;
```

`TABLE_ROWS` de InnoDB es estimación, no conteo exacto; tamaños son aproximados y pueden no reflejar inmediatamente toda variación. Opcional: benchmark de **INSERT/UPDATE aislado en clon** antes/después de índices para cuantificar mantenimiento. No escribir sobre el dataset medido principal.

Valorar por caso: (i) reducción real de latencia/filas/IO, (ii) estabilidad p95, (iii) tamaño adicional, (iv) posible sobreindexación en `ep2_orders`, (v) frecuencia estimada de uso y ROI cualitativo. **No conservar los cinco índices por defecto**: Q1/Q3/Q4/Q5 compiten en la misma tabla; en un escenario real decidir cuáles aportan suficiente valor frente al costo en escrituras.

### Fase 5 — Informe y gráficos

Informe con: contexto del negocio y fuente de datos; instalación y validación; perfilado, distribuciones e índices iniciales; entorno; metodología común (fechas, repetición, caché, concurrencia, herramientas); sección idéntica para Q1–Q5; tablas comparativas A/B/C; al menos gráfico de barras p50 A/B/C por consulta y gráfico de filas examinadas; evaluación de efectos secundarios y **al menos dos mejoras futuras** (ej.: índices alternativos basados en cardinalidad real, partición solo tras aumento de volumen, mejora del modelo de estados/pagos, estadísticas/capacidad, pruebas de concurrencia y escalado).

## 5. Plantillas para completar con resultados verdaderos

### 5.1 Ficha obligatoria por consulta

```text
ID: Q__ / nombre: ___________________________
Necesidad de negocio y frecuencia esperada: ___________________________
Parámetros/ventana/sucursal/región: ___________________________
Filas devueltas y checksum A/B/C: ___________________________
Síntoma 1 OBSERVADO en A (operador / métrica): ___________________________
Síntoma 2 OBSERVADO en A (operador / métrica): ___________________________
H1 (reescritura): Si ..., entonces ... porque ...; evidencia que la refuta: ...
H2 (índice): Si ..., entonces ... porque ...; evidencia que la refuta: ...
Cambios B (SQL y justificación): ___________________________
Cambios C (CREATE INDEX y justificación): ___________________________
Plan A/B/C: scan, access/index, filas estimadas/reales, loops, sort, temporales.
Riesgos: mantenimiento, espacio, selectividad, concurrencia, límites del entorno.
Conclusión: H1 confirmada/no confirmada; H2 confirmada/no confirmada; priorizar/rechazar.
```

### 5.2 Tabla comparativa (una por consulta)

| Métrica | A: original | B: reescritura | C: + índice | B vs A | C vs B | C vs A |
|---|---:|---:|---:|---:|---:|---:|
| Mediana latencia cliente (ms) | | | | | | |
| Media latencia cliente (ms) | | | | | | |
| p95 (ms) | | | | | | |
| `TIMER_WAIT` promedio (ms), si disponible | | | | | | |
| Filas examinadas promedio | | | | | | |
| Filas devueltas | | | | | | |
| Filas reales relevantes del plan | | | | | | |
| Sort / temporales | | | | | | |
| Lecturas lógicas (delta; indicar fuente) | | | | | | |
| Lecturas físicas (delta global aislado, opcional) | | | | | | |
| CPU promedio proceso durante lote (%) | | | | | | |
| Throughput bajo carga fija (qps) | | | | | | |
| Tamaño índice adicional (bytes) | | | | | | |
| Plan: operaciones/índices utilizados | | | | — | — | — |

**Cálculos:** `% mejora latencia A→C = 100 × (latencia_A - latencia_C) / latencia_A`; un número negativo es **regresión**. Para throughput (mayor es mejor), `% cambio = 100 × (qps_C - qps_A) / qps_A`. No calcular porcentajes si el denominador es cero; reportar N/A. Para filas/lecturas, indicar exactamente el contador utilizado. **No sumar porcentajes A→B y B→C**: calcular siempre a partir de valores reales.

### 5.3 Evidencias exactas que debes devolverme para construir el informe

```text
EP2/
  00_parametros.sql                  # valores fijos, sin secretos
  00_entorno.md                      # versión, hardware, MySQL config, herramientas
  01_dataset.txt                     # conteos, distribución, SHOW CREATE/INDEX
  01_consultas_before.sql            # Q1...Q5 originales
  02_explain_before.sql              # EXPLAIN de Q1...Q5
  03_optimizaciones.sql              # reescrituras, CREATE INDEX y rollbacks ordenados
  04_consultas_after.sql             # reescritas B (también usadas en C)
  05_explain_after.sql               # EXPLAIN de B y C
  evidencias/
    Q1_A_tree.txt; Q1_A_analyze.txt; Q1_A_tiempos.csv; Q1_A_metricas.txt; Q1_A_os_pidstat.txt
    Q1_B_tree.txt; Q1_B_analyze.txt; Q1_B_tiempos.csv; Q1_B_metricas.txt; Q1_B_os_pidstat.txt
    Q1_C_tree.txt; Q1_C_analyze.txt; Q1_C_tiempos.csv; Q1_C_metricas.txt; Q1_C_os_pidstat.txt
    ... repetir exactamente para Q2, Q3, Q4 y Q5 ...
    Q1_resultados_A.csv; Q1_resultados_B.csv; Q1_resultados_C.csv
    ... repetir resultados/checksums para Q2...Q5 ...
    indice_tamanios_antes_despues.csv
  resultados_comparativos.csv        # fila por consulta y fase, métricas consolidadas
  informe_EP2.md                     # redactar después de medir
```

Si solo puedes entregar una primera tanda, prioriza: **`01_dataset.txt`, `00_entorno.md`, cinco planes A (`TREE` + `ANALYZE`), tiempos de A, y `SHOW INDEX`**. Con ello podremos validar los cuellos reales y, si hace falta, ajustar hipótesis/índices *antes de ejecutar optimizaciones*. En una segunda tanda envía B/C, tiempo, filas/IO y monitoreo OS.

**Capturas sugeridas (complementarias a archivos):** conteos de tres tablas obligatorias; esquema e índices; cada plan A/C; tiempo de ejecución y plan asociado a consulta; PerfMon/`pidstat` de **lotes**, etiquetado con Qn y fase; comparación final. Nunca entregar solo captura sin SQL/identificación de la corrida.

## 6. Criterio de éxito y advertencias para defender el trabajo

- **Éxito técnico:** mismo resultado, menos trabajo real (filas/IO/sort/loops) y/o menor latencia con varianza controlada; índice utilizado donde aporta. **Éxito académico:** demostrar procedimiento causal, incluyendo casos sin mejora.
- **No declarar “faltan índices en los JOIN”** sin mirar PK/FK creadas automáticamente.
- **No afirmar que CPU disminuyó por consulta** a partir de CPU global o de una captura puntual.
- **No confundir agregación comercial de pedidos** con recaudación efectiva debido a las incoherencias aleatorias del dataset.
- **No inventar lentitud ni optimización:** puede que el optimizador ya elija buen plan, que `EXISTS` se transforme internamente, que el sort final sea inevitable, o que el índice no se use. Todos esos hallazgos son discutibles y documentables.
- **No mezclar transformaciones:** el cambio A→B aisla SQL, B→C aisla índice (dentro de los límites de cache/estadísticas). Esto facilita hipótesis refutables en cada caso.
- **No confundir mejora puntual con impacto organizacional:** frecuencia de consulta y costo de escrituras deben ponderarse al decidir conservar índices.

**Secuencia recomendada para empezar:** ejecutar §1 y enviarme `01_dataset.txt` + cinco `EXPLAIN ANALYZE` de etapa A (junto con `SHOW INDEX`) antes de crear índices. Así confirmaremos empíricamente qué hipótesis vale la pena sostener en el informe.
