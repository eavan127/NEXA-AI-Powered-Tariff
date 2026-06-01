# NEXA — Module C: Landed Cost Calculator — Design Spec

**Date:** 2026-06-02
**Author:** NEXA Team (EileenYJH)
**Status:** Approved — ready for implementation
**Deadline:** Day 1 Pitch 24 June 2026 · Final 2 July 2026

---

## 1. Overview

Module C is the third and final stage of the NEXA AI tariff pipeline. It receives the HS code from Module A and the best FTA rate from Module B, then computes the full legally-correct Malaysian landed cost per shipment — broken down per SKU — and persists results to Supabase for the audit trail.

**Pipeline position:**
```
Module A (HS Classification)
  └─► Module B (FTA Matching)
        └─► Module C (Landed Cost Calculator)  ← this spec
              └─► landed_costs table (Supabase)
                    └─► Frontend Module C card
```

**Value to judges:** Demonstrates the complete data pipeline story — all three modules writing to Supabase, with human-readable cost breakdown, LMW toggle for scenario comparison, and anti-dumping duty detection.

---

## 2. Architecture & Data Flow

### Approach: Backend calculation (Python), persisted to Supabase

All math lives in Python. The frontend auto-triggers Module C immediately after Module B succeeds — no extra analyst click needed.

```
Frontend (index.html / app.js)
  │
  ├── triggerB() → POST /api/match-fta/{id}          ← existing
  │        └─ on success → auto-calls triggerC(id)    ← NEW
  │
  └── triggerC() → POST /api/calculate-landed-cost/{id}  ← NEW endpoint
           │
           ├── reads: shipments table (CIF components, bom_items, weight)
           ├── reads: fta_results table (best_fta_rate_pct, mfn_rate_pct)
           ├── reads: config table (FX rate, LMW flag, fee defaults)
           ├── reads: anti_dumping_orders lookup
           │
           ├── computes: per-SKU pipeline (Steps 1–5)
           ├── computes: shipment-level consolidation
           │
           ├── writes: landed_costs table (with cost_breakdown JSONB)
           └── returns: full cost breakdown JSON → frontend populates Module C card
```

**New files:**
- `backend/calculator/landed_cost.py` — all calculation logic
- One new `POST` route in `backend/api/routes.py`

**No schema changes** — `landed_costs` table already exists with all required columns.

---

## 3. Calculation Logic

### Pre-condition: bom_items JSONB field structure

Each SKU in `bom_items` must contain:

```json
{
  "hs_code": "8534.00",
  "description": "PCB Assembly",
  "quantity": 50,
  "unit_value_usd": 240.00,
  "weight_kg": 0.8
}
```

`line_total_value_usd = unit_value_usd × quantity` — always use the line total, never the unit price alone, for apportionment and valuation.

---

### Step 1 — Rule 2: Freight & Insurance Apportionment (Industry Standard)

Freight is split by **weight**; insurance is split by **value**. This is the RMCD-accepted industry standard.

```
line_total_value_usd  = unit_value_usd × quantity

SKU_freight_usd       = total_freight_usd   × (sku_weight_kg        / Σ all sku_weight_kg)
SKU_insurance_usd     = total_insurance_usd × (line_total_value_usd / Σ all line_total_value_usd)

SKU_CIF_MYR           = (line_total_value_usd + SKU_freight_usd + SKU_insurance_usd) × RMCD_FX
```

**Fallback:** If `total_weight_kg = 0` (weight data missing), apportion freight by value proportion instead.

**RMCD_FX** is the official Royal Malaysian Customs Department valuation exchange rate, stored in the `config` table as `RMCD_FX_MYR_PER_USD`. RMCD assesses all duties in MYR — CIF must be in MYR before any duty calculation.

---

### Step 2 — Rule 1: LMW / FIZ Eligibility Check

**LMW (Licensed Manufacturing Warehouse)** and **FIZ (Free Industrial Zone)** facilities are exempt from customs duty and sales tax under Malaysian law. Jabil's Malaysian plants hold LMW licences.

```
Config flag: is_lmw_facility  (boolean, stored in config table)

IF is_lmw_facility == True:
    customs_duty_myr = 0

IF is_lmw_facility == False:
    customs_duty_myr = SKU_CIF_MYR × (best_fta_rate_pct / 100)
```

**Legal basis:** Sales Tax Act 2018 (Persons Exempted from Payment of Tax) Order, and the Customs Act 1967 (Licensed Manufacturing Warehouse) Regulations.

**Demo value:** Toggle `is_lmw_facility` between `true` and `false` to show judges the dramatic cost difference between an optimised LMW supply chain versus a standard commercial import.

---

### Step 3 — Rule 3: Anti-Dumping Duty (ADD)

Malaysia's RMCD imposes anti-dumping duties on certain goods from specific origin countries. ADD is assessed directly against `SKU_CIF_MYR` (not the post-duty value).

```
Lookup: (origin_country, hs_chapter)  →  anti_dumping_rate_pct

IF match found:
    ADD_myr = round(SKU_CIF_MYR × (anti_dumping_rate_pct / 100), 4)

IF no match:
    ADD_myr = 0
    anti_dumping_matched = False
```

**Seeded anti-dumping orders (POC):**

| Origin  | HS Chapter | Rate % | Context |
|---------|-----------|--------|---------|
| China   | 7210      | 13.9   | Cold-rolled steel products |
| China   | 8541      | 5.0    | Discrete semiconductor components |
| Vietnam | 7214      | 8.5    | Steel rebar |

---

### Step 4 — Sales Tax (Legal RMCD Compounding Structure)

Malaysia's **Sales Tax rate on goods is 10%** (Sales Tax Act 2018). This is distinct from the 6% Service Tax, which applies to services only.

Sales Tax is computed on the cumulative total of CIF + all duties — this compounding is the legally correct RMCD structure.

```
IF is_lmw_facility == True:
    sales_tax_myr = 0

IF is_lmw_facility == False:
    sales_tax_myr = round(0.10 × (SKU_CIF_MYR + customs_duty_myr + ADD_myr), 4)
```

---

### Step 5 — SKU Total

```
SKU_total_myr = SKU_CIF_MYR + customs_duty_myr + ADD_myr + sales_tax_myr
```

---

### Shipment-Level Consolidation

Material CIF and imposed taxes are kept separate to keep dashboard metrics clean. Do **not** sum `SKU_total_myr` into the duties figure — that double-counts the material cost.

```
Total_Material_CIF_MYR     = Σ SKU_CIF_MYR
Total_Duties_Taxes_MYR     = Σ (customs_duty_myr + ADD_myr + sales_tax_myr)

Processing_Fee_MYR         = rmcd_declaration_fee_myr               (50.00)
                           + base_clearance_fee_myr                  (300.00)
                           + (handling_fee_per_kg_myr × total_kg)    (2.50/kg)
                           + terminal_handling_myr                   (120.00)
                           + edi_fee_myr                             (15.00)

Total_Landed_MYR           = Total_Material_CIF_MYR
                           + Total_Duties_Taxes_MYR
                           + Processing_Fee_MYR

Total_Landed_USD           = round(Total_Landed_MYR / RMCD_FX, 4)
```

**Why divide by RMCD_FX (not multiply by USD_PER_MYR separately):** `Processing_Fee_MYR` consists of raw MYR-denominated local charges. Dividing the full `Total_Landed_MYR` by `RMCD_FX` correctly converts both duty-derived MYR amounts and local operational expenses back to USD for Jabil's corporate ledger in one clean step.

---

### Precision & Rounding Rules

Floating-point division errors accumulate across large shipment volumes. Apply these rules throughout `landed_cost.py`:

- **All intermediate values:** `round(val, 4)` in Python
- **All DB storage:** Use Supabase `NUMERIC` columns — never `FLOAT`
- **Display / reporting:** `round(val, 2)` only at the final output layer

---

## 4. Config Table Defaults

Seeded into the existing `config` table at startup:

| Key | Default Value | Notes |
|-----|--------------|-------|
| `RMCD_FX_MYR_PER_USD` | `4.67` | RMCD official rate — update bi-weekly |
| `is_lmw_facility` | `true` | Toggle for LMW vs commercial demo |
| `sales_tax_rate_pct` | `10.0` | Malaysia Sales Tax Act 2018 |
| `rmcd_declaration_fee_myr` | `50.0` | Flat K1 fee per declaration |
| `base_clearance_fee_myr` | `300.0` | Forwarder/agent base clearance rate |
| `handling_fee_per_kg_myr` | `2.50` | Per-kg handling charge |
| `terminal_handling_myr` | `120.0` | Port terminal handling |
| `edi_fee_myr` | `15.0` | Electronic data interchange fee |

---

## 5. cost_breakdown JSONB Structure

Stored in `landed_costs.cost_breakdown` — one entry per SKU, providing full line-item audit detail.

```json
[
  {
    "sku_id": "8534.00",
    "description": "PCB Assembly",
    "apportionment_metrics": {
      "line_total_value_usd": 12000.00,
      "allocated_freight_usd": 142.50,
      "allocated_insurance_usd": 22.10,
      "calculated_cif_myr": 56852.37
    },
    "regulatory_charges_myr": {
      "applied_fta_rate_pct": 0.0,
      "customs_duty_charged": 0.0,
      "anti_dumping_duty_charged": 0.0,
      "sales_tax_charged": 0.0
    },
    "flags_applied": {
      "is_lmw_facility": true,
      "anti_dumping_matched": false
    }
  }
]
```

---

## 6. bom_items Seed Data Update

All 5 sample shipments need `quantity` and `weight_kg` added to each SKU. Example (SHIP001):

```python
"bom_items": [
    {"hs_code": "8534.00", "description": "PCB Assembly",
     "quantity": 50, "unit_value_usd": 240.00, "weight_kg": 0.8},
    {"hs_code": "8541.10", "description": "Diode",
     "quantity": 200, "unit_value_usd": 10.00, "weight_kg": 0.02}
]
```

---

## 7. Frontend Changes

### Auto-trigger chain (`js/app.js`)

```javascript
// After triggerB() succeeds:
async function triggerB() {
  // ... existing Module B call ...
  // on success:
  await triggerC(shipmentId)   // auto-chain — no analyst click needed
}

async function triggerC(shipmentId) {
  // POST /api/calculate-landed-cost/{id}
  // populate Module C card on success
  // show amber warning on error
}
```

### Module C card updates (`index.html`)

| Element | Before | After |
|---------|--------|-------|
| Status badge | `⬅ Build This` (amber) | `Calculating…` → `Complete` (teal) or `Error` (amber) |
| Formula rows | Static placeholder text | Live values: CIF MYR, Duty, ADD, Sales Tax, Processing Fee |
| `mcTotal` | `Awaiting Module C` | `Total_Landed_USD` in large display |
| New: LMW indicator | — | Green chip "LMW Exempt" or muted "Commercial Entry" |
| New: ADD alert | — | Amber chip "ADD Applied" (hidden if no match) |

---

## 8. Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Module B not yet run | `triggerC()` blocked — checks `fta_results` exists before calling |
| `total_weight_kg = 0` | Fallback: apportion freight by value proportion |
| `RMCD_FX_MYR_PER_USD` missing from config | Returns 500 with message: "FX rate not configured — seed config table" |
| Anti-dumping: no match | `ADD = 0`, flag `anti_dumping_matched: false` — not an error |
| LMW = true | Duty and Sales Tax both 0; only Processing Fee applies |

---

## 9. API Endpoint

```
POST /api/calculate-landed-cost/{shipment_id}

Response (200):
{
  "status": "ok",
  "data": {
    "shipment_id": "SHIP001",
    "total_landed_usd": 1842.30,
    "total_landed_myr": 8601.54,
    "total_material_cif_myr": 7421.00,
    "total_duties_taxes_myr": 695.54,
    "processing_fee_myr": 485.00,
    "is_lmw_facility": true,
    "cost_breakdown": [ ... per-SKU array ... ]
  }
}
```

---

## 10. Malaysian Trade Compliance Glossary

| Term | Definition |
|------|-----------|
| **CIF** | Cost, Insurance & Freight — the RMCD customs valuation basis |
| **LMW** | Licensed Manufacturing Warehouse — RMCD-licensed facility exempt from customs duty and sales tax |
| **FIZ** | Free Industrial Zone — similar exemption status to LMW |
| **ADD** | Anti-Dumping Duty — additional duty imposed on goods priced below fair market value from specific origins |
| **RMCD** | Royal Malaysian Customs Department (Kastam Diraja Malaysia) |
| **K1** | Import declaration form submitted to RMCD per shipment |
| **MFN** | Most Favoured Nation — default WTO tariff rate applied when no FTA qualifies |
| **FTA** | Free Trade Agreement — preferential duty rate under bilateral/multilateral trade treaty |
| **Sales Tax** | 10% tax on goods under Malaysia Sales Tax Act 2018 (not the 6% Service Tax) |
| **EDI** | Electronic Data Interchange — electronic customs submission fee |
| **RMCD_FX** | Official RMCD customs valuation exchange rate, set by Bank Negara Malaysia and published bi-weekly |
