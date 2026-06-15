-- 001_compliance_cases.sql
-- Compliance workflow: Cases 1/2/3 for tariff rate changes
-- Run against Supabase SQL editor

-- ── Shipments: new transit fields ────────────────────────────────
ALTER TABLE shipments
  ADD COLUMN IF NOT EXISTS vessel_loading_date    DATE,
  ADD COLUMN IF NOT EXISTS estimated_arrival_date DATE,
  ADD COLUMN IF NOT EXISTS transport_mode         TEXT,
  ADD COLUMN IF NOT EXISTS bill_of_lading_number  TEXT,
  ADD COLUMN IF NOT EXISTS vessel_name            TEXT,
  ADD COLUMN IF NOT EXISTS port_of_loading        TEXT,
  ADD COLUMN IF NOT EXISTS regulatory_flag        TEXT;

-- Expand status enum to include in_transit, customs_hold, submitted
ALTER TABLE shipments DROP CONSTRAINT IF EXISTS shipments_status_check;
ALTER TABLE shipments ADD CONSTRAINT shipments_status_check
  CHECK(status IN ('pending','flagged','approved','rejected','in_transit','customs_hold','submitted'));

-- ── Audit trail: role tracking ────────────────────────────────────
ALTER TABLE audit_trail ADD COLUMN IF NOT EXISTS role_required TEXT;

-- ── Regulatory alerts table ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS regulatory_alerts (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  hs_code              TEXT NOT NULL,
  old_rate             NUMERIC NOT NULL,
  new_rate             NUMERIC NOT NULL,
  effective_date       DATE NOT NULL,
  affected_shipment_ids JSONB DEFAULT '[]',
  detected_at          TIMESTAMPTZ DEFAULT NOW(),
  status               TEXT DEFAULT 'active' CHECK(status IN ('active','resolved'))
);

-- ── Test shipments for compliance case demo ───────────────────────

-- SHIP011 — Case 1 (pending, aluminium extrusions Vietnam→US)
INSERT INTO shipments (
  sap_shipment_id, product_description,
  shipment_value_usd, freight_cost_usd, insurance_cost_usd,
  destination_country, origin_country, bom_items, status
) VALUES (
  'SHIP011', 'Aluminium Extrusions 6061-T6 — HS 7604.29',
  45000, 1200, 180, 'US', 'Vietnam',
  '[{"sku_id":"AL-EXT-6061","description":"Aluminium extrusion profile 6061-T6","quantity":500,"unit_value_usd":80,"weight_kg":2.4}]'::jsonb,
  'pending'
) ON CONFLICT (sap_shipment_id) DO UPDATE SET
  status = 'pending', regulatory_flag = NULL;

-- SHIP012 — Case 2 (approved, not yet shipped)
INSERT INTO shipments (
  sap_shipment_id, product_description,
  shipment_value_usd, freight_cost_usd, insurance_cost_usd,
  destination_country, origin_country, bom_items, status
) VALUES (
  'SHIP012', 'Aluminium Extrusions 6061-T6 — HS 7604.29',
  38000, 950, 140, 'US', 'Vietnam',
  '[{"sku_id":"AL-EXT-6061","description":"Aluminium extrusion profile 6061-T6","quantity":420,"unit_value_usd":80,"weight_kg":2.4}]'::jsonb,
  'approved'
) ON CONFLICT (sap_shipment_id) DO UPDATE SET
  status = 'approved', regulatory_flag = NULL;

-- SHIP013 — Case 3 (in-transit, vessel already departed)
INSERT INTO shipments (
  sap_shipment_id, product_description,
  shipment_value_usd, freight_cost_usd, insurance_cost_usd,
  destination_country, origin_country, bom_items, status,
  vessel_loading_date, estimated_arrival_date,
  transport_mode, bill_of_lading_number, vessel_name, port_of_loading
) VALUES (
  'SHIP013', 'Aluminium Extrusions 6061-T6 — HS 7604.29',
  52000, 1400, 210, 'US', 'Vietnam',
  '[{"sku_id":"AL-EXT-6061","description":"Aluminium extrusion profile 6061-T6","quantity":580,"unit_value_usd":80,"weight_kg":2.4}]'::jsonb,
  'in_transit',
  '2026-05-30', '2026-06-25',
  'SEA', 'MYLA2026051234', 'MV PACIFIC BRIDGE', 'Port Klang (WESTPORT)'
) ON CONFLICT (sap_shipment_id) DO UPDATE SET
  status = 'in_transit',
  vessel_loading_date    = '2026-05-30',
  estimated_arrival_date = '2026-06-25',
  transport_mode         = 'SEA',
  bill_of_lading_number  = 'MYLA2026051234',
  vessel_name            = 'MV PACIFIC BRIDGE',
  port_of_loading        = 'Port Klang (WESTPORT)',
  regulatory_flag        = NULL;
