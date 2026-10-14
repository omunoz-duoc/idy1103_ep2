-- ============================================================
-- IDY1103 - Evaluación Parcial 2 (EP2)
-- Dataset de práctica para análisis de rendimiento / optimización
-- Opción A: Archivo SQL (schema + carga de datos) por motor
--
-- ============================================================

/* #########################################################################
   2) MYSQL 8+ (MariaDB 10.2+ con CTE recursivo también suele funcionar)
   ######################################################################### */
SET SESSION cte_max_recursion_depth = 10000000;
-- === LIMPIEZA (MySQL) ===
DROP TABLE IF EXISTS ep2_payments;
DROP TABLE IF EXISTS ep2_order_items;
DROP TABLE IF EXISTS ep2_orders;
DROP TABLE IF EXISTS ep2_products;
DROP TABLE IF EXISTS ep2_customers;
DROP TABLE IF EXISTS ep2_stores;

-- === ESQUEMA (MySQL) ===
CREATE TABLE ep2_customers (
  customer_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  full_name   VARCHAR(120) NOT NULL,
  email       VARCHAR(160) NOT NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  city        VARCHAR(60) NOT NULL,
  segment     VARCHAR(30) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE ep2_products (
  product_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  product_name VARCHAR(120) NOT NULL,
  category     VARCHAR(40) NOT NULL,
  price        DECIMAL(10,2) NOT NULL,
  is_active    TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB;

CREATE TABLE ep2_stores (
  store_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  store_name VARCHAR(80) NOT NULL,
  region     VARCHAR(40) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE ep2_orders (
  order_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id BIGINT NOT NULL,
  store_id    BIGINT NOT NULL,
  order_ts    DATETIME NOT NULL,
  status      VARCHAR(20) NOT NULL,
  total_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES ep2_customers(customer_id),
  CONSTRAINT fk_orders_store    FOREIGN KEY (store_id) REFERENCES ep2_stores(store_id)
) ENGINE=InnoDB;

CREATE TABLE ep2_order_items (
  item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  order_id   BIGINT NOT NULL,
  product_id BIGINT NOT NULL,
  qty        INT NOT NULL,
  unit_price DECIMAL(10,2) NOT NULL,
  CONSTRAINT fk_items_order   FOREIGN KEY (order_id) REFERENCES ep2_orders(order_id),
  CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES ep2_products(product_id)
) ENGINE=InnoDB;

CREATE TABLE ep2_payments (
  payment_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  order_id BIGINT NOT NULL,
  paid_ts  DATETIME NOT NULL,
  method   VARCHAR(20) NOT NULL,
  amount   DECIMAL(12,2) NOT NULL,
  CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES ep2_orders(order_id)
) ENGINE=InnoDB;

-- === CARGA DE DATOS (MySQL) ===
-- Nota:
--   Se generan secuencias con CTE recursivo. Requiere MySQL 8+.

-- -- Stores (20)
INSERT INTO ep2_stores(store_name, region)
SELECT CONCAT('Sucursal ', n) AS store_name,
       ELT(1 + FLOOR(RAND()*4), 'RM','Maule','Biobío','Valparaíso') AS region
FROM (
  WITH RECURSIVE seq AS (
    SELECT 1 AS n
    UNION ALL
    SELECT n + 1 FROM seq WHERE n < 20
  )
  SELECT n FROM seq
) s;

-- -- Customers (5000)
INSERT INTO ep2_customers(full_name, email, created_at, city, segment)
SELECT
  CONCAT('Cliente ', n),
  CONCAT('cliente', n, '@mail.cl'),
  NOW() - INTERVAL FLOOR(RAND()*365) DAY,
  ELT(1 + FLOOR(RAND()*5), 'Santiago','Talca','Curicó','Concepción','Valparaíso'),
  ELT(1 + FLOOR(RAND()*3), 'Retail','Mayorista','Online')
FROM (
  WITH RECURSIVE seq AS (
    SELECT 1 AS n
    UNION ALL
    SELECT n + 1 FROM seq WHERE n < 5000
  )
  SELECT n FROM seq
) s;

-- -- Products (2000)
INSERT INTO ep2_products(product_name, category, price, is_active)
SELECT
  CONCAT('Producto ', n),
  ELT(1 + FLOOR(RAND()*5), 'Fertilizante','Riego','Herramienta','Semilla','Protección'),
  ROUND(RAND()*50000 + 500, 2),
  IF(RAND() > 0.05, 1, 0)
FROM (
  WITH RECURSIVE seq AS (
    SELECT 1 AS n
    UNION ALL
    SELECT n + 1 FROM seq WHERE n < 2000
  )
  SELECT n FROM seq
) s;

-- -- Orders (20000)
INSERT INTO ep2_orders(customer_id, store_id, order_ts, status, total_amount)
SELECT
  1 + FLOOR(RAND()*5000),
  1 + FLOOR(RAND()*20),
  NOW() - INTERVAL FLOOR(RAND()*180) DAY,
  ELT(1 + FLOOR(RAND()*4), 'CREATED','PAID','SHIPPED','CANCELLED'),
  0
FROM (
  WITH RECURSIVE seq AS (
    SELECT 1 AS n
    UNION ALL
    SELECT n + 1 FROM seq WHERE n < 20000
  )
  SELECT n FROM seq
) s;

-- -- Order Items (100000)
INSERT INTO ep2_order_items(order_id, product_id, qty, unit_price)
SELECT
  1 + FLOOR(RAND()*20000),
  1 + FLOOR(RAND()*2000),
  1 + FLOOR(RAND()*5),
  ROUND(RAND()*50000 + 500, 2)
FROM (
  WITH RECURSIVE seq AS (
    SELECT 1 AS n
    UNION ALL
    SELECT n + 1 FROM seq WHERE n < 100000
  )
  SELECT n FROM seq
) s;

-- -- Payments (15000)
INSERT INTO ep2_payments(order_id, paid_ts, method, amount)
SELECT
  1 + FLOOR(RAND()*20000),
  NOW() - INTERVAL FLOOR(RAND()*180) DAY,
  ELT(1 + FLOOR(RAND()*3), 'CARD','TRANSFER','CASH'),
  ROUND(RAND()*200000 + 1000, 2)
FROM (
  WITH RECURSIVE seq AS (
    SELECT 1 AS n
    UNION ALL
    SELECT n + 1 FROM seq WHERE n < 15000
  )
  SELECT n FROM seq
) s;

-- -- Actualiza total_amount (MySQL)
-- -- Nota: si tienes SQL_SAFE_UPDATES activado, desactívalo temporalmente:
SET SQL_SAFE_UPDATES = 0;
UPDATE ep2_orders o
JOIN (
  SELECT order_id, ROUND(SUM(qty * unit_price), 2) AS sum_total
  FROM ep2_order_items
  GROUP BY order_id
) s ON o.order_id = s.order_id
SET o.total_amount = s.sum_total;
SET SQL_SAFE_UPDATES = 1;


-- ============================================================
-- FIN DEL ARCHIVO
-- ============================================================
