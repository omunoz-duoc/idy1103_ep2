USE ep2_lab;

SELECT 'customers' AS table_name, COUNT(*) AS row_count FROM ep2_customers
UNION ALL SELECT 'orders', COUNT(*) FROM ep2_orders
UNION ALL SELECT 'order_items', COUNT(*) FROM ep2_order_items
UNION ALL SELECT 'payments', COUNT(*) FROM ep2_payments
UNION ALL SELECT 'products', COUNT(*) FROM ep2_products
UNION ALL SELECT 'stores', COUNT(*) FROM ep2_stores;

SHOW CREATE TABLE ep2_orders;
SHOW CREATE TABLE ep2_order_items;
SHOW INDEX FROM ep2_orders;
SHOW INDEX FROM ep2_order_items;
SHOW INDEX FROM ep2_payments;
SHOW INDEX FROM ep2_customers;
SHOW INDEX FROM ep2_products;
SHOW INDEX FROM ep2_stores;

SELECT MIN(order_ts) AS first_order, MAX(order_ts) AS last_order,
       COUNT(DISTINCT customer_id) AS customers_with_orders
FROM ep2_orders;
SELECT status, COUNT(*) AS row_count FROM ep2_orders GROUP BY status;
SELECT method, COUNT(*) AS row_count FROM ep2_payments GROUP BY method;
SELECT category, COUNT(*) AS row_count FROM ep2_products GROUP BY category;
SELECT city, segment, COUNT(*) AS row_count FROM ep2_customers GROUP BY city, segment;

SELECT COUNT(*) AS orders_without_items
FROM ep2_orders o
WHERE NOT EXISTS (SELECT 1 FROM ep2_order_items i WHERE i.order_id=o.order_id);

SELECT COUNT(*) AS paid_orders_without_payment
FROM ep2_orders o
WHERE o.status='PAID'
  AND NOT EXISTS (SELECT 1 FROM ep2_payments p WHERE p.order_id=o.order_id);

SELECT COUNT(*) AS payments_for_cancelled_orders
FROM ep2_payments p
JOIN ep2_orders o ON o.order_id=p.order_id
WHERE o.status='CANCELLED';
