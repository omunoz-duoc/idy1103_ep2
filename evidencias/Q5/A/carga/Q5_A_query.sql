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
