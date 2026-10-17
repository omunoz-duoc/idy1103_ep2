-- OPCIONAL. Ejecutar como administrador, antes de todas las mediciones.
-- Todo queda comentado: copiar solo los permisos deseados, ajustando usuario/host.
-- La suite funciona sin estos permisos y registra los diagnósticos no disponibles.

-- GRANT SELECT ON performance_schema.threads TO 'ep2_runner'@'localhost';
-- GRANT SELECT ON performance_schema.events_statements_history TO 'ep2_runner'@'localhost';
-- GRANT SELECT ON performance_schema.events_statements_history_long TO 'ep2_runner'@'localhost';
-- GRANT SELECT ON performance_schema.setup_consumers TO 'ep2_runner'@'localhost';
-- GRANT SELECT ON performance_schema.setup_instruments TO 'ep2_runner'@'localhost';
-- GRANT SELECT ON performance_schema.table_io_waits_summary_by_index_usage TO 'ep2_runner'@'localhost';
-- GRANT SELECT ON performance_schema.data_locks TO 'ep2_runner'@'localhost';
-- GRANT SELECT ON performance_schema.data_lock_waits TO 'ep2_runner'@'localhost';
-- GRANT SELECT ON mysql.innodb_index_stats TO 'ep2_runner'@'localhost';

-- Estos permisos exponen metadatos de observabilidad de la instancia.
-- No se requiere PROCESS para ejecutar el benchmark; sin él las conexiones
-- visibles en PROCESSLIST están limitadas al usuario actual.
-- Si habilita consumidores/instrumentos, hágalo antes de A y mantenga idéntica
-- configuración durante A/B/C. La suite intenta history si history_long está OFF.
