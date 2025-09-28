-- sale_demo.sql  (records a sale + updates inventory + cash)
-- Run with psql -v vars (see command below)

BEGIN;

-- ---- Inputs (via -v) ----
-- :tenant   demo tenant UUID
-- :loc      location UUID
-- :sku1/:qty1/:price1  first line
-- :sku2/:qty2/:price2  second line (optional: pass qty2=0 to skip)

-- 1) Build line items from SKUs + join to product IDs
WITH items AS (
  SELECT :sku1::text AS sku, :qty1::numeric AS qty, :price1::numeric AS unit_price, 0::numeric AS discount
  UNION ALL
  SELECT :sku2::text, :qty2::numeric, :price2::numeric, 0::numeric
),
prods AS (
  SELECT i.sku, i.qty, i.unit_price, i.discount, p.id AS product_id
  FROM items i
  JOIN product p
    ON p.tenant_id = :'tenant'
   AND p.sku = i.sku
  WHERE i.qty > 0
),
totals AS (
  SELECT
    SUM(qty * unit_price - discount)::numeric(12,2) AS subtotal,
    ROUND(SUM(qty * unit_price - discount) * 0.10, 2)::numeric(12,2) AS tax  -- 10% demo tax
  FROM prods
),
ins_sale AS (
  INSERT INTO sale (tenant_id, location_id, subtotal, tax, total, metadata)
  VALUES (
    :'tenant', :'loc',
    (SELECT subtotal FROM totals),
    (SELECT tax FROM totals),
    (SELECT subtotal + tax FROM totals),
    '{}'::jsonb
  )
  RETURNING id
),
ins_items AS (
  INSERT INTO sale_item (tenant_id, sale_id, product_id, qty, unit_price, discount)
  SELECT :'tenant', (SELECT id FROM ins_sale), product_id, qty, unit_price, discount
  FROM prods
  RETURNING 1
),
ins_tender AS (
  INSERT INTO sale_tender (tenant_id, sale_id, method, amount, status, details)
  VALUES (
    :'tenant', (SELECT id FROM ins_sale), 'cash',
    (SELECT subtotal + tax FROM totals), 'approved', '{}'::jsonb
  )
  RETURNING 1
),
ins_cash AS (
  INSERT INTO cash_movement (tenant_id, location_id, sale_id, type, amount, note)
  VALUES (
    :'tenant', :'loc', (SELECT id FROM ins_sale),
    'cash_sale', (SELECT subtotal + tax FROM totals), 'cash tender'
  )
  RETURNING 1
)
-- 2) Inventory: write negative stock movements for the sale
INSERT INTO stock_movement (tenant_id, product_id, location_id, delta_qty, reason, ref_id)
SELECT
  :'tenant', product_id, :'loc', -qty, 'sale', (SELECT id FROM ins_sale)
FROM prods;

COMMIT;

-- 3) Refresh snapshot and show new on-hand
REFRESH MATERIALIZED VIEW inventory_current;

SELECT p.sku, p.name, ic.on_hand
FROM inventory_current ic
JOIN product p ON p.id = ic.product_id
WHERE ic.tenant_id = :'tenant'
ORDER BY p.sku;
