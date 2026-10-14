USE ep2_lab;
-- Run once after loading and validating the dataset, before any A measurement.
ANALYZE TABLE ep2_customers, ep2_products, ep2_stores,
              ep2_orders, ep2_order_items, ep2_payments;
