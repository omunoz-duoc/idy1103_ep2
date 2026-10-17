# Evidencias Q1

Resumen automático de esta corrida. La interpretación causal se completa revisando los planes.

| Perfil | Etapa | Iteraciones | Mediana ms | p95 ms | Evidencia |
|---|---|---:|---:|---:|---|
| micro | A | 30 | 1.332985 | 1.615937 | [resumen](A/micro/Q1_A_summary.json) |
| carga | A | 10000 | 1.060604 | 1.234453 | [resumen](A/carga/Q1_A_summary.json) |
| micro | B | 30 | 1.271272 | 1.47565 | [resumen](B/micro/Q1_B_summary.json) |
| carga | B | 10000 | 1.083499 | 1.273667 | [resumen](B/carga/Q1_B_summary.json) |
| micro | C | 30 | 0.622778 | 0.842079 | [resumen](C/micro/Q1_C_summary.json) |
| carga | C | 10000 | 0.576454 | 0.683604 | [resumen](C/carga/Q1_C_summary.json) |

- Equivalencia de resultados: [equivalencia.json](equivalencia.json).
- Comparar A→B para la reescritura y B→C para el efecto incremental del índice.
- Interpretación de los operadores y dos causas observadas: __________________
- Impacto de negocio, frecuencia y costo de escritura: __________________
- Capturas y condiciones manuales: __________________
- Los archivos availability.json y COBERTURA.md explican las métricas faltantes.
