SELECT p.method, COUNT(*) AS operaciones,
       SUM(p.amount) AS monto_total, AVG(p.amount) AS ticket_medio
FROM ep2_payments p
WHERE p.method=@method AND p.paid_ts>=@start_ts AND p.paid_ts<@end_ts
GROUP BY p.method;
