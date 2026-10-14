USE ep2_lab;
SELECT NOW() AS collected_at, VERSION() AS mysql_version,
       @@version_comment AS distribution;
SHOW VARIABLES WHERE Variable_name IN (
  'performance_schema', 'innodb_buffer_pool_size', 'cte_max_recursion_depth',
  'max_connections', 'optimizer_switch', 'slow_query_log', 'long_query_time'
);
SHOW GLOBAL STATUS WHERE Variable_name IN ('Threads_connected', 'Threads_running');
SELECT NAME, ENABLED
FROM performance_schema.setup_consumers
WHERE NAME IN ('events_statements_current', 'events_statements_history',
               'events_statements_history_long', 'events_waits_current');
