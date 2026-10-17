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
