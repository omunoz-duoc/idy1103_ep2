-- IMPORTANT: run only the CREATE for the case currently being measured at stage C.
-- Run its DROP immediately after collecting that case's stage-C evidence.
-- All statements are commented out intentionally. Copy only the two statements
-- for the case being tested into your SQL client; do not run this whole file.

-- Q1 C
-- CREATE INDEX idx_ep2_q1_store_status_ts
-- ON ep2_orders(store_id, status, order_ts DESC, order_id DESC);
-- If MySQL removed the implicit FK index, restore it before dropping Q1:
-- CREATE INDEX fk_orders_store ON ep2_orders(store_id);
-- DROP INDEX idx_ep2_q1_store_status_ts ON ep2_orders;

-- Q2 C
-- CREATE INDEX idx_ep2_q2_method_ts_amount
-- ON ep2_payments(method, paid_ts, amount);
-- DROP INDEX idx_ep2_q2_method_ts_amount ON ep2_payments;

-- Q3 C
-- CREATE INDEX idx_ep2_q3_order_ts
-- ON ep2_orders(order_ts, order_id);
-- DROP INDEX idx_ep2_q3_order_ts ON ep2_orders;

-- Q4 C
-- CREATE INDEX idx_ep2_q4_cust_status_ts
-- ON ep2_orders(customer_id, status, order_ts);
-- If MySQL removed the implicit FK index, restore it before dropping Q4:
-- CREATE INDEX fk_orders_customer ON ep2_orders(customer_id);
-- DROP INDEX idx_ep2_q4_cust_status_ts ON ep2_orders;

-- Q5 C
-- CREATE INDEX idx_ep2_q5_store_ts_status_total
-- ON ep2_orders(store_id, order_ts, status, total_amount);
-- If MySQL removed the implicit FK index, restore it before dropping Q5:
-- CREATE INDEX fk_orders_store ON ep2_orders(store_id);
-- DROP INDEX idx_ep2_q5_store_ts_status_total ON ep2_orders;
