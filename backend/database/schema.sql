CREATE EXTENSION IF NOT EXISTS vector;

-- 1. shipments - one row per shipment from SAP 
CREATE TABLE shipments (
    id UUID PRIMARY KEY
    DEFAULT gen_random_uuid(),
    sap_shipment_id TEXT UNIQUE NOT NULL,
    product_description TEXT NOT NULL,
    shipment_value_usd NUMERIC NOT NULL,
    freight_cost_usd NUMERIC DEFAULT 0,
    insurance_cost_usd NUMERIC DEFAULT 0,
    destination_country TEXT NOT NULL,
    origin_country TEXT,
    bom_items JSONB DEFAULT '[]',
    status TEXT DEFAULT 'pending'
CHECK(status IN ('pending','flagged','approved','rejected')),
created_at TIMESTAMPTZ DEFAULT NOW(),
updated_at TIMESTAMPTZ DEFAULT NOW()
);

--2. HS-classifications (module A)
CREATE TABLE hs_classifications(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id UUID REFERENCES shipments(id),
    e2open_hs_code TEXT,
    ai_hs_code TEXT,
    confidence_score NUMERIC,
    reasoning_text TEXT,
    rag_sources JSONB,
    analyst_override_hs TEXT,
    final_hs_code TEXT,
    module_a_status TEXT
CHECK(module_a_status IN ('auto_passed','flagged_disagree','flagged_low_confidence')),
created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. FTA_results (module b)
CREATE TABLE fta_results(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id UUID REFERENCES shipments(id),
    applicable_ftas JSONB,
    best_fta_name TEXT,
    best_fta_rate_pct NUMERIC,
    mfn_rate_pct NUMERIC,
    roo_type TEXT CHECK(roo_type IN('RVC','tariff_shift','wholly_obtained','specific_process')),
    roo_passed BOOLEAN,
    rvc_supplier_declared NUMERIC,
    rvc_threshold NUMERIC,
    duty_saving_usd NUMERIC,
    module_b_status TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. landed_costs (module C)
CREATE TABLE landed_costs(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id UUID REFERENCES shipments(id),
    cif_value_usd NUMERIC, -- insurance+freight+product value
    duty_amount_usd NUMERIC,
    duty_rate_applied_pct NUMERIC,
    gst_amount_usd NUMERIC,
    other_fees_usd NUMERIC,
    total_landed_cost_usd NUMERIC,
    mfn_scenario_cost_usd NUMERIC,
    fta_saving_usd NUMERIC,
    cost_breakdown JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. audit_trail - immutable log of every decision 
CREATE TABLE audit_trail (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id UUID REFERENCES shipments(id),
    event_type TEXT NOT NULL,
    module_name TEXT,
    input_snapshot JSONB,
    output_snapshot JSONB,
    confidence_score NUMERIC,
    analyst_id TEXT,
    analyst_action TEXT,
    analyst_note TEXT,
    reasoning_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. tariff_rates - MFN rates form WTO API
CREATE TABLE tariff_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hs_code TEXT NOT NULL,
    country_code TEXT NOT NULL,
    mfn_rate_pct NUMERIC,
    source TEXT,
    effective_date DATE,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(hs_code,country_code)
);

-- 7. fta_coverage 
CREATE TABLE fta_coverage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fta_name TEXT UNIQUE NOT NULL,
    member_countries TEXT[],
    effective_date DATE
);

-- 8. fta_rates - preferential duty rates per fta
CREATE TABLE fta_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fta_name TEXT NOT NULL,
    hs_code TEXT NOT NULL,
    preferential_rate_pct NUMERIC,
    origin_country TEXT,
    effective_date DATE,
    UNIQUE(fta_name,hs_code,origin_country)
);

--9. roo_rules - rules of origin per fta 
CREATE TABLE roo_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fta_name TEXT NOT NULL,
    hs_code TEXT NOT NULL,
    roo_type TEXT,
CHECK(roo_type IN('RVC','tariff_shift','wholly_obtained','specific_process')),
    rvc_threshold_pct NUMERIC,
    tariff_shift_description TEXT,
    wholly_obtained_criteria TEXT,
    specific_process_description TEXT,
    source_url TEXT
);

--10. HS_references - WCO definitions + embeddings for RAG
CREATE TABLE hs_reference (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hs_code TEXT UNIQUE NOT NULL,
    description TEXT,
    explanatory_notes TEXT,
    source TEXT,
    embedding VECTOR(768)
);

--11. gazette_alerts 
CREATE TABLE gazette_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gazette_title TEXT,
    gazette_url TEXT,
    published_date DATE,
    is_tariff_related BOOLEAN,
    extracted_rates JSONB,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- indexes to speed up common queries 
-- ivfflate a special algorithm for vector math (similarity search) = faster retrieval
CREATE INDEX ON hs_reference USING ivfflat(embedding vector_cosine_ops);
--cosine measure the angle between two vectors ( a math to measure similarity )
CREATE INDEX ON shipments(status);
CREATE INDEX ON audit_trail(shipment_id);
-- can search quickly based on index, instead of searching string one by one