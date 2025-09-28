-- seed.sql (idempotent)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- constants
\set tenant 00000000-0000-0000-0000-000000000001
\set loc_id 0b49a234-8c92-48b1-9000-aaaaaaaaaaaa
\set prod_a_id cbc6279a-ec68-4c09-8c70-a96ced83aad4
\set prod_b_id 77d86511-baaa-44c5-b4df-2d42f4bb23bb

-- 1) Location (upsert by primary key)
INSERT INTO location (id, tenant_id, name, timezone)
VALUES (:'loc_id', :'tenant', 'Main Store', 'UTC')
ON CONFLICT (id) DO NOTHING;

-- 2) Products (upsert by unique (tenant_id, sku))
INSERT INTO product (id, tenant_id, sku, name, category, unit, metadata)
VALUES (:'prod_a_id', :'tenant', '1001', 'Coca Cola 500ml', 'Beverages', 'ea', '{}'::jsonb)
ON CONFLICT (tenant_id, sku) DO NOTHING;

INSERT INTO product (id, tenant_id, sku, name, category, unit, metadata)
VALUES (:'prod_b_id', :'tenant', '2002', 'Lays Chips 100g', 'Snacks', 'ea', '{}'::jsonb)
ON CONFLICT (tenant_id, sku) DO NOTHING;

-- 3) Opening stock (insert only if not already present)
INSERT INTO stock_movement (id, tenant_id, product_id, location_id, delta_qty, reason, ref_id)
SELECT gen_random_uuid(), :'tenant', :'prod_a_id', :'loc_id', 50, 'adjustment', NULL
WHERE NOT EXISTS (
  SELECT 1 FROM stock_movement
  WHERE tenant_id = :'tenant' AND product_id = :'prod_a_id' AND location_id = :'loc_id' AND reason = 'adjustment'
);

INSERT INTO stock_movement (id, tenant_id, product_id, location_id, delta_qty, reason, ref_id)
SELECT gen_random_uuid(), :'tenant', :'prod_b_id', :'loc_id', 30, 'adjustment', NULL
WHERE NOT EXISTS (
  SELECT 1 FROM stock_movement
  WHERE tenant_id = :'tenant' AND product_id = :'prod_b_id' AND location_id = :'loc_id' AND reason = 'adjustment'
);

-- 4) Refresh snapshot and show
REFRESH MATERIALIZED VIEW inventory_current;

SELECT p.sku, p.name, ic.location_id, ic.on_hand
FROM inventory_current ic
JOIN product p ON p.id = ic.product_id
WHERE ic.tenant_id = :'tenant'
ORDER BY p.sku;
