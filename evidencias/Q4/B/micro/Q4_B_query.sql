SELECT c.customer_id, c.full_name, c.city, c.segment
FROM ep2_customers c
WHERE c.city=@city AND c.segment=@segment
  AND EXISTS (SELECT 1 FROM ep2_orders o
              WHERE o.customer_id=c.customer_id AND o.status='PAID'
                AND o.order_ts>=@long_start_ts AND o.order_ts<@end_ts)
ORDER BY c.customer_id;
