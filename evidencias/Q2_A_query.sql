SELECT p.method, COUNT(*) AS operaciones,
       SUM(p.amount) AS monto_total, AVG(p.amount) AS ticket_medio
FROM ep2_payments p
WHERE p.method=@method
  AND DATE(p.paid_ts)>=DATE(@start_ts)
  AND DATE(p.paid_ts)<DATE(@end_ts)
GROUP BY p.method;
