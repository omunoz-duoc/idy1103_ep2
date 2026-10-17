SELECT o.order_id, o.customer_id, o.order_ts, o.total_amount
FROM ep2_orders o
WHERE o.store_id=@store_id AND o.status='CREATED'
  AND DATE(o.order_ts)>=DATE(@long_start_ts)
  AND DATE(o.order_ts)<DATE(@end_ts)
ORDER BY o.order_ts DESC, o.order_id DESC
LIMIT 50;
