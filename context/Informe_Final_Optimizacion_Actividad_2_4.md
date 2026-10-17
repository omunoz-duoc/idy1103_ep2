# Informe Final — Optimización de Consultas (Actividad 2.4)

> **IL2.4:** Documenta las técnicas de ajuste aplicadas, justificando las decisiones tomadas para respaldar los resultados obtenidos.
>
> **Instrucciones:** Completa esta plantilla con tu análisis. Mantén evidencia clara y trazable por consulta (Consulta 1 / Consulta 2), incluyendo Antes/Después, tablas comparativas y conclusiones técnicas (**evidencia → causa → efecto**).

---

## Datos del estudiante

| Campo | Valor |
|---|---|
| Nombre y apellido | _Completar_ |
| Sección / Jornada | _Completar_ |
| Motor y versión (MySQL/PostgreSQL) | _Completar_ |
| Entorno y herramienta (local/cloud; Workbench/pgAdmin/otra) | _Completar_ |
| Fecha de entrega | _Completar_ |

## Checklist de entrega (verifica antes de subir)

- [ ] Incluí al menos 2 consultas (Consulta 1 y Consulta 2) con SQL exacto.
- [ ] Adjunté evidencia ANTES y DESPUÉS por cada consulta: EXPLAIN (captura o salida) + métricas (tiempo y otras disponibles).
- [ ] Construí tabla comparativa antes vs después por consulta (diferencia y/o porcentaje).
- [ ] Incluí al menos 1 gráfico simple (barras Antes vs Después) con datos consistentes.
- [ ] Redacté interpretación técnica por consulta (2–4 líneas) conectando evidencia → causa → efecto.
- [ ] Agregué conclusiones finales y trade-offs/limitaciones (caché, carga, costo en escrituras, etc.).
- [ ] Incluí enlace a la cápsula audiovisual (2–3 min) y verifiqué que el acceso sea público o con permisos correctos.

---

## 1. Resumen ejecutivo

*En 5–7 líneas: problema, técnica(s) aplicada(s) y mejora(s) lograda(s) **con números**.*

_Escribe aquí tu resumen ejecutivo._

## 2. Contexto y descripción de la base de datos

*Tablas relevantes, volumen aproximado (filas) y propósito del conjunto de datos.*

_Escribe aquí._

## 3. Problema de rendimiento y objetivo

*Qué observaste (síntoma) y cuál fue tu objetivo. Ej.: reducir el tiempo de X a Y, o disminuir filas procesadas.*

_Escribe aquí._

## 4. Metodología de medición (línea base)

*Condiciones, número de ejecuciones, indicadores usados (tiempo, CPU, I/O, filas procesadas) y por qué son comparables.*

_Escribe aquí._

---

## 5.1 Análisis — Consulta 1

### Propósito de la consulta

_¿Qué busca obtener esta consulta?_

### SQL exacto

```sql
-- Pega aquí tu consulta SQL (sin modificar)
```

### Evidencia ANTES (línea base)

*Incluye EXPLAIN / EXPLAIN ANALYZE y métricas observadas.*

| Indicador | Antes | Después | Diferencia | % Mejora |
|---|---|---|---|---|
| Tiempo (ms o s) | | | | |
| _Otro indicador_ | | | | |
| _Otro indicador_ | | | | |

**EXPLAIN (ANTES):**

```text
Inserta captura o pega salida aquí.
```

### Técnica(s) aplicada(s) y justificación

*Describe el ajuste (índice, reescritura, parámetro), el motivo y la hipótesis técnica.*

- **Ajuste aplicado:** _Completar_
- **Justificación (por qué corresponde):** _Completar_
- **Script / comando usado (si aplica):**

```sql
-- CREATE INDEX u otros comandos
```

### Evidencia DESPUÉS

*Repite la medición en condiciones equivalentes y registra EXPLAIN / monitoreo.*

**EXPLAIN (DESPUÉS):**

```text
Inserta captura o pega salida aquí.
```

### Comparación e interpretación (evidencia → causa → efecto)

*En 2–4 líneas: qué cambió (plan/métricas) y por qué mejora (o no) el rendimiento.*

_Escribe aquí._

---

## 5.2 Análisis — Consulta 2

### Propósito de la consulta

_¿Qué busca obtener esta consulta?_

### SQL exacto

```sql
-- Pega aquí tu consulta SQL (sin modificar)
```

### Evidencia ANTES (línea base)

*Incluye EXPLAIN / EXPLAIN ANALYZE y métricas observadas.*

| Indicador | Antes | Después | Diferencia | % Mejora |
|---|---|---|---|---|
| Tiempo (ms o s) | | | | |
| _Otro indicador_ | | | | |
| _Otro indicador_ | | | | |

**EXPLAIN (ANTES):**

```text
Inserta captura o pega salida aquí.
```

### Técnica(s) aplicada(s) y justificación

*Describe el ajuste (índice, reescritura, parámetro), el motivo y la hipótesis técnica.*

- **Ajuste aplicado:** _Completar_
- **Justificación (por qué corresponde):** _Completar_
- **Script / comando usado (si aplica):**

```sql
-- CREATE INDEX u otros comandos
```

### Evidencia DESPUÉS

*Repite la medición en condiciones equivalentes y registra EXPLAIN / monitoreo.*

**EXPLAIN (DESPUÉS):**

```text
Inserta captura o pega salida aquí.
```

### Comparación e interpretación (evidencia → causa → efecto)

*En 2–4 líneas: qué cambió (plan/métricas) y por qué mejora (o no) el rendimiento.*

_Escribe aquí._

---

## 6. Comparación final (síntesis)

*Impacto global: qué consulta mejoró más y por qué.*

| Consulta | Mejora principal (tiempo/filas/I/O) | Técnica aplicada | Evidencia clave (EXPLAIN/métrica) |
|---|---|---|---|
| Consulta 1 | | | |
| Consulta 2 | | | |

## 7. Conclusiones y recomendaciones

*Con base en evidencia: qué ajustes funcionaron, cuáles no, y recomendaciones concretas.*

_Escribe aquí._

## 8. Implicancias, trade-offs y limitaciones

*Al menos 2 (ej.: costo en escrituras por índices, variabilidad por caché/carga, limitaciones del entorno).*

- **Implicancia 1:** _Completar_
- **Implicancia 2:** _Completar_

### Cápsula audiovisual (2–3 min) — guion en 4 puntos

1. Contexto + problema
2. Técnica(s) aplicada(s) y por qué
3. Evidencia antes vs después (tabla/gráfico + 1 captura)
4. Conclusión + trade-off

## 9. Anexos (opcional)

*Scripts, capturas adicionales o enlaces a archivos que no caben en el cuerpo del informe.*

_Adjunta aquí._
