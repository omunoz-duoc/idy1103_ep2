USE ep2_lab;

SELECT DATE(MAX(order_ts)) + INTERVAL 1 DAY AS end_ts,
       DATE(MAX(order_ts)) + INTERVAL 1 DAY - INTERVAL 14 DAY AS start_ts,
       DATE(MAX(order_ts)) + INTERVAL 1 DAY - INTERVAL 90 DAY AS long_start_ts
FROM ep2_orders;

SELECT store_id, COUNT(*) AS created_orders
FROM ep2_orders
WHERE status='CREATED'
GROUP BY store_id
ORDER BY created_orders DESC
LIMIT 5;

SELECT method, COUNT(*) AS payments FROM ep2_payments GROUP BY method ORDER BY payments DESC;
SELECT city, segment, COUNT(*) AS customers
FROM ep2_customers GROUP BY city, segment ORDER BY customers DESC;
SELECT region, COUNT(*) AS stores FROM ep2_stores GROUP BY region ORDER BY stores DESC;
