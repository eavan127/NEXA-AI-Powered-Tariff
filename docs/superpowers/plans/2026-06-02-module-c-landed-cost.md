# Module C — Landed Cost Calculator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Module C Landed Cost Calculator — a Python engine that computes the full Malaysian landed cost (CIF apportionment, LMW exemption, anti-dumping duty, 10% sales tax, processing fees), persists results to Supabase, and populates the frontend Module C card with live MYR/USD breakdown data.

**Architecture:** `landed_cost.py` holds all calculation logic as pure functions testable without Supabase. A new `POST /api/calculate-landed-cost/{shipment_id}` route reads from `shipments`/`fta_results`/`config`, calls the calculator, writes to `landed_costs`. The frontend auto-chains Module C after Module B succeeds, replacing the "Awaiting Module C" placeholder with the live cost breakdown.

**Tech Stack:** Python 3.11, FastAPI, supabase-py, pytest, Vanilla JS (no framework)

---

## Pre-requisite: Sync the feature branch

`feature/layer3-landed-cost` is behind `main` and missing all backend files. Run this before starting any task:

```bash
git checkout feature/layer3-landed-cost
git merge main --no-edit
git push origin feature/layer3-landed-cost
```

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/calculator/landed_cost.py` | CIF apportionment, LMW, ADD, sales tax, consolidation, Supabase write |
| Create | `backend/tests/__init__.py` | Makes tests/ a package |
| Create | `backend/tests/test_landed_cost.py` | Unit tests — no Supabase needed |
| Modify | `backend/seed_database.py` | Add quantity/weight_kg to bom_items; add seed_config() |
| Modify | `backend/api/routes.py` | Add POST /api/calculate-landed-cost/{shipment_id} |
| Modify | `js/api.js` | Add runModuleC(shipmentId) |
| Modify | `index.html` | Add id="modCBadge", Run C buttons, id="pipeCCount" |
| Modify | `js/app.js` | Add triggerC, runSingleC, update renderModuleCCard, table dot, pipeline count, doBulk |

---

## Task 1: Update seed data — bom_items + config

**Files:**
- Modify: `backend/seed_database.py`

The current `bom_items` lack `quantity` and `weight_kg`, which are required for freight/insurance apportionment. The `config` table needs FX rate and fee defaults.

- [ ] **Step 1: Replace the five `bom_items` entries in `SAMPLE_SHIPMENTS`**

In `backend/seed_database.py`, find the `SAMPLE_SHIPMENTS` list and replace each `"bom_items"` value:

```python
# SHIP001 — PCB Assembly, Vietnam
"bom_items": [
    {"hs_code": "8534.00", "description": "PCB Assembly",
     "quantity": 50, "unit_value_usd": 240.00, "weight_kg": 0.8},
    {"hs_code": "8541.10", "description": "Diode",
     "quantity": 200, "unit_value_usd": 10.00, "weight_kg": 0.02},
],

# SHIP002 — Industrial Servo Motor, China
"bom_items": [
    {"hs_code": "8501.52", "description": "Servo Motor",
     "quantity": 5, "unit_value_usd": 1400.00, "weight_kg": 12.5},
    {"hs_code": "8537.10", "description": "Motor Controller",
     "quantity": 5, "unit_value_usd": 300.00, "weight_kg": 1.2},
],

# SHIP003 — Aluminium Heatsink Extrusion, Vietnam
"bom_items": [
    {"hs_code": "7604.29", "description": "Aluminium Heatsink Extrusion",
     "quantity": 100, "unit_value_usd": 28.00, "weight_kg": 0.8},
],

# SHIP004 — DRAM Memory Module DDR5, Taiwan
"bom_items": [
    {"hs_code": "8542.31", "description": "DRAM Module DDR5",
     "quantity": 300, "unit_value_usd": 55.00, "weight_kg": 0.05},
],

# SHIP005 — Optical Lens Assembly, South Korea
"bom_items": [
    {"hs_code": "9001.90", "description": "Optical Lens Assembly",
     "quantity": 40, "unit_value_usd": 520.00, "weight_kg": 0.15},
],
```

- [ ] **Step 2: Add `seed_config()` function after `seed_mock_classifications()`**

```python
async def seed_config() -> None:
    CONFIG_DEFAULTS = [
        ("RMCD_FX_MYR_PER_USD",     "4.67"),
        ("is_lmw_facility",          "true"),
        ("sales_tax_rate_pct",       "10.0"),
        ("rmcd_declaration_fee_myr", "50.0"),
        ("base_clearance_fee_myr",   "300.0"),
        ("handling_fee_per_kg_myr",  "2.50"),
        ("terminal_handling_myr",    "120.0"),
        ("edi_fee_myr",              "15.0"),
    ]
    try:
        for key, value in CONFIG_DEFAULTS:
            supabase.table("config").upsert(
                {"key": key, "value": value}, on_conflict="key"
            ).execute()
        print("[seed] ✓ Config defaults seeded")
    except Exception as e:
        print(f"[seed] Config seed failed: {e}")
```

- [ ] **Step 3: Call `seed_config()` from `run_seed()`**

In `run_seed()`, add after `await seed_additional_fta_data()`:

```python
await seed_config()
```

- [ ] **Step 4: Commit**

```bash
git add backend/seed_database.py
git commit -m "feat(seed): add bom_items quantities/weights and seed config defaults for Module C"
```

---

## Task 2: Create `landed_cost.py` — calculation engine

**Files:**
- Create: `backend/calculator/landed_cost.py`

All math lives in `compute_sku_costs()` (pure, testable). `calculate_landed_cost()` is the only function that touches Supabase.

- [ ] **Step 1: Create `backend/calculator/landed_cost.py`**

```python
from supabase import Client

# Malaysian RMCD anti-dumping orders: (origin_country, hs_chapter_4) → rate_pct
ANTI_DUMPING_ORDERS = {
    ("China",   "7210"): 13.9,   # Cold-rolled steel products
    ("China",   "8541"): 5.0,    # Discrete semiconductor components
    ("Vietnam", "7214"): 8.5,    # Steel rebar
}


def get_anti_dumping_rate(origin_country: str, hs_code: str) -> float:
    chapter = (hs_code or "")[:4]
    return ANTI_DUMPING_ORDERS.get((origin_country, chapter), 0.0)


def compute_sku_costs(
    sku: dict,
    total_freight_usd: float,
    total_insurance_usd: float,
    total_bom_value_usd: float,
    total_weight_kg: float,
    fx: float,
    lmw: bool,
    fta_rate_pct: float,
    origin: str,
) -> dict:
    qty        = float(sku.get("quantity", 1))
    unit_val   = float(sku.get("unit_value_usd", 0))
    weight     = float(sku.get("weight_kg", 0))
    hs         = sku.get("hs_code", "")
    line_total = round(unit_val * qty, 4)

    # Step 1 — Freight apportioned by weight; insurance by value
    if total_weight_kg > 0:
        sku_freight = round(total_freight_usd * (weight * qty / total_weight_kg), 4)
    elif total_bom_value_usd > 0:
        sku_freight = round(total_freight_usd * (line_total / total_bom_value_usd), 4)
    else:
        sku_freight = 0.0

    sku_insurance = (
        round(total_insurance_usd * (line_total / total_bom_value_usd), 4)
        if total_bom_value_usd > 0 else 0.0
    )

    sku_cif_myr = round((line_total + sku_freight + sku_insurance) * fx, 4)

    # Step 2 — LMW/FIZ: duty exempt if licensed
    customs_duty = 0.0 if lmw else round(sku_cif_myr * (fta_rate_pct / 100), 4)

    # Step 3 — Anti-Dumping Duty (assessed on CIF directly)
    add_rate    = get_anti_dumping_rate(origin, hs)
    add_myr     = round(sku_cif_myr * (add_rate / 100), 4) if add_rate > 0 else 0.0
    add_matched = add_rate > 0

    # Step 4 — Sales Tax 10% (compounds on CIF + all duties; 0% under LMW)
    sales_tax = (
        0.0 if lmw
        else round(0.10 * (sku_cif_myr + customs_duty + add_myr), 4)
    )

    return {
        "sku_id":      hs,
        "description": sku.get("description", ""),
        "apportionment_metrics": {
            "line_total_value_usd":    line_total,
            "allocated_freight_usd":   sku_freight,
            "allocated_insurance_usd": sku_insurance,
            "calculated_cif_myr":      sku_cif_myr,
        },
        "regulatory_charges_myr": {
            "applied_fta_rate_pct":      fta_rate_pct,
            "customs_duty_charged":      customs_duty,
            "anti_dumping_duty_charged": add_myr,
            "sales_tax_charged":         sales_tax,
        },
        "flags_applied": {
            "is_lmw_facility":      lmw,
            "anti_dumping_matched": add_matched,
        },
        # internal helpers stripped before DB write
        "_sku_cif_myr": sku_cif_myr,
        "_duties_myr":  round(customs_duty + add_myr + sales_tax, 4),
    }


async def calculate_landed_cost(shipment_id: str, supabase: Client) -> dict:
    # Load shipment
    ship_res = supabase.table("shipments").select(
        "id, sap_shipment_id, origin_country, "
        "shipment_value_usd, freight_cost_usd, insurance_cost_usd, bom_items"
    ).eq("sap_shipment_id", shipment_id).execute()
    if not ship_res.data:
        return {"error": f"Shipment {shipment_id} not found"}
    ship = ship_res.data[0]

    # Load latest FTA result (Module B must have run first)
    fta_res = supabase.table("fta_results").select(
        "best_fta_rate_pct, mfn_rate_pct, best_fta_name"
    ).eq("shipment_id", ship["id"]).order("created_at", desc=True).limit(1).execute()
    if not fta_res.data:
        return {"error": f"No FTA result for {shipment_id} — run Module B first"}
    fta      = fta_res.data[0]
    fta_rate = float(fta["best_fta_rate_pct"] or 0)
    mfn_rate = float(fta["mfn_rate_pct"] or 5.0)

    # Load config
    cfg_res = supabase.table("config").select("key, value").execute()
    cfg     = {r["key"]: r["value"] for r in cfg_res.data}
    fx              = float(cfg.get("RMCD_FX_MYR_PER_USD",     "4.67"))
    lmw             = cfg.get("is_lmw_facility", "true").lower() == "true"
    rmcd_fee        = float(cfg.get("rmcd_declaration_fee_myr",  "50.0"))
    base_clearance  = float(cfg.get("base_clearance_fee_myr",    "300.0"))
    handling_per_kg = float(cfg.get("handling_fee_per_kg_myr",   "2.50"))
    terminal        = float(cfg.get("terminal_handling_myr",     "120.0"))
    edi             = float(cfg.get("edi_fee_myr",               "15.0"))

    bom = ship["bom_items"] or []
    if not bom:
        return {"error": f"No bom_items for {shipment_id}"}

    total_freight   = float(ship["freight_cost_usd"] or 0)
    total_insurance = float(ship["insurance_cost_usd"] or 0)
    origin          = ship["origin_country"] or ""

    total_bom_value = round(sum(
        float(s.get("unit_value_usd", 0)) * float(s.get("quantity", 1)) for s in bom
    ), 4)
    total_weight_kg = round(sum(
        float(s.get("weight_kg", 0)) * float(s.get("quantity", 1)) for s in bom
    ), 4)

    # Per-SKU pipeline (Steps 1–4)
    sku_results = [
        compute_sku_costs(
            sku, total_freight, total_insurance,
            total_bom_value, total_weight_kg,
            fx, lmw, fta_rate, origin
        )
        for sku in bom
    ]

    # Shipment-level consolidation
    total_cif_myr    = round(sum(s["_sku_cif_myr"] for s in sku_results), 4)
    total_duties_myr = round(sum(s["_duties_myr"]  for s in sku_results), 4)
    processing_fee   = round(
        rmcd_fee + base_clearance + (handling_per_kg * total_weight_kg) + terminal + edi, 4
    )
    total_landed_myr = round(total_cif_myr + total_duties_myr + processing_fee, 4)
    total_landed_usd = round(total_landed_myr / fx, 4)

    # MFN scenario (for savings comparison; LMW → only processing fee)
    mfn_duties_myr   = round(sum(s["_sku_cif_myr"] * (mfn_rate / 100) for s in sku_results), 4)
    mfn_sales_tax    = round(0.10 * (total_cif_myr + mfn_duties_myr), 4) if not lmw else 0.0
    mfn_scenario_usd = round(
        (total_cif_myr + mfn_duties_myr + mfn_sales_tax + processing_fee) / fx, 4
    )
    fta_saving_usd   = round(max(0.0, mfn_scenario_usd - total_landed_usd), 4)

    # Strip internal fields before DB write
    breakdown = [
        {k: v for k, v in s.items() if not k.startswith("_")}
        for s in sku_results
    ]

    supabase.table("landed_costs").insert({
        "shipment_id":           ship["id"],
        "cif_value_usd":         round(total_cif_myr / fx, 4),
        "duty_amount_usd":       round(total_duties_myr / fx, 4),
        "duty_rate_applied_pct": fta_rate,
        "gst_amount_usd":        round(
            sum(s["regulatory_charges_myr"]["sales_tax_charged"] for s in breakdown) / fx, 4
        ),
        "other_fees_usd":        round(processing_fee / fx, 4),
        "total_landed_cost_usd": total_landed_usd,
        "mfn_scenario_cost_usd": mfn_scenario_usd,
        "fta_saving_usd":        fta_saving_usd,
        "cost_breakdown":        breakdown,
    }).execute()

    print(
        f"[landed_cost] ✓ {shipment_id} → USD {total_landed_usd} (MYR {total_landed_myr})"
        f" | LMW={lmw} | {fta['best_fta_name']} {fta_rate}%"
    )

    return {
        "shipment_id":            shipment_id,
        "is_lmw_facility":        lmw,
        "fx_rate":                fx,
        "total_material_cif_myr": total_cif_myr,
        "total_duties_taxes_myr": total_duties_myr,
        "processing_fee_myr":     processing_fee,
        "total_landed_myr":       total_landed_myr,
        "total_landed_usd":       total_landed_usd,
        "mfn_scenario_usd":       mfn_scenario_usd,
        "fta_saving_usd":         fta_saving_usd,
        "best_fta_name":          fta["best_fta_name"],
        "fta_rate_pct":           fta_rate,
        "cost_breakdown":         breakdown,
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/calculator/landed_cost.py
git commit -m "feat(module-c): add landed_cost.py calculation engine (CIF, LMW, ADD, SST)"
```

---

## Task 3: Unit tests for the calculation math

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_landed_cost.py`

No Supabase needed. Run from the `backend/` directory.

- [ ] **Step 1: Create `backend/tests/__init__.py`** (empty file)

```bash
# From backend/ directory (PowerShell):
New-Item -ItemType File tests\__init__.py -Force
```

- [ ] **Step 2: Create `backend/tests/test_landed_cost.py`**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calculator.landed_cost import compute_sku_costs, get_anti_dumping_rate

FX = 4.67


class TestAntiDumping:
    def test_china_8541_matches(self):
        assert get_anti_dumping_rate("China", "8541.10") == 5.0

    def test_china_7210_matches(self):
        assert get_anti_dumping_rate("China", "7210.61") == 13.9

    def test_vietnam_7214_matches(self):
        assert get_anti_dumping_rate("Vietnam", "7214.20") == 8.5

    def test_vietnam_8534_no_match(self):
        assert get_anti_dumping_rate("Vietnam", "8534.00") == 0.0

    def test_unknown_origin_no_match(self):
        assert get_anti_dumping_rate("Taiwan", "8541.10") == 0.0


class TestSkuCosts:
    def test_lmw_true_no_duty_no_tax(self):
        sku = {"hs_code": "8534.00", "description": "PCB",
               "quantity": 10, "unit_value_usd": 100.0, "weight_kg": 0.5}
        r = compute_sku_costs(sku, 100.0, 20.0, 1000.0, 5.0, FX, True, 0.0, "Vietnam")
        assert r["regulatory_charges_myr"]["customs_duty_charged"] == 0.0
        assert r["regulatory_charges_myr"]["sales_tax_charged"] == 0.0

    def test_lmw_false_duty_calculated(self):
        sku = {"hs_code": "8501.52", "description": "Motor",
               "quantity": 1, "unit_value_usd": 1000.0, "weight_kg": 10.0}
        r = compute_sku_costs(sku, 0.0, 0.0, 1000.0, 10.0, FX, False, 5.0, "China")
        expected_cif  = round(1000.0 * FX, 4)
        expected_duty = round(expected_cif * 0.05, 4)
        assert r["regulatory_charges_myr"]["customs_duty_charged"] == expected_duty

    def test_sales_tax_compounds_on_cif_plus_duties(self):
        sku = {"hs_code": "8501.52", "description": "Motor",
               "quantity": 1, "unit_value_usd": 1000.0, "weight_kg": 10.0}
        r = compute_sku_costs(sku, 0.0, 0.0, 1000.0, 10.0, FX, False, 5.0, "China")
        cif  = r["apportionment_metrics"]["calculated_cif_myr"]
        duty = r["regulatory_charges_myr"]["customs_duty_charged"]
        add  = r["regulatory_charges_myr"]["anti_dumping_duty_charged"]
        tax  = r["regulatory_charges_myr"]["sales_tax_charged"]
        assert tax == round(0.10 * (cif + duty + add), 4)

    def test_freight_apportioned_by_weight(self):
        sku = {"hs_code": "8534.00", "description": "PCB",
               "quantity": 1, "unit_value_usd": 100.0, "weight_kg": 2.0}
        r = compute_sku_costs(sku, 100.0, 0.0, 500.0, 10.0, FX, True, 0.0, "Vietnam")
        # weight 2/10 = 20%
        assert r["apportionment_metrics"]["allocated_freight_usd"] == round(100.0 * (2.0 / 10.0), 4)

    def test_insurance_apportioned_by_value(self):
        sku = {"hs_code": "8534.00", "description": "PCB",
               "quantity": 1, "unit_value_usd": 250.0, "weight_kg": 1.0}
        r = compute_sku_costs(sku, 0.0, 50.0, 500.0, 5.0, FX, True, 0.0, "Vietnam")
        # value 250/500 = 50%
        assert r["apportionment_metrics"]["allocated_insurance_usd"] == round(50.0 * 0.5, 4)

    def test_add_triggered_for_china_8541(self):
        sku = {"hs_code": "8541.10", "description": "Diode",
               "quantity": 1, "unit_value_usd": 1000.0, "weight_kg": 0.1}
        r = compute_sku_costs(sku, 0.0, 0.0, 1000.0, 0.1, FX, True, 0.0, "China")
        cif          = r["apportionment_metrics"]["calculated_cif_myr"]
        expected_add = round(cif * 0.05, 4)
        assert r["regulatory_charges_myr"]["anti_dumping_duty_charged"] == expected_add
        assert r["flags_applied"]["anti_dumping_matched"] is True

    def test_freight_fallback_to_value_when_weight_zero(self):
        sku = {"hs_code": "8534.00", "description": "PCB",
               "quantity": 1, "unit_value_usd": 200.0, "weight_kg": 0.0}
        r = compute_sku_costs(sku, 100.0, 0.0, 400.0, 0.0, FX, True, 0.0, "Vietnam")
        # value fallback: 200/400 = 50%
        assert r["apportionment_metrics"]["allocated_freight_usd"] == round(100.0 * 0.5, 4)
```

- [ ] **Step 3: Run the tests (expect all to pass)**

```bash
# From backend/ directory:
cd backend
pytest tests/test_landed_cost.py -v
```

Expected:
```
PASSED tests/test_landed_cost.py::TestAntiDumping::test_china_8541_matches
PASSED tests/test_landed_cost.py::TestAntiDumping::test_china_7210_matches
PASSED tests/test_landed_cost.py::TestAntiDumping::test_vietnam_7214_matches
PASSED tests/test_landed_cost.py::TestAntiDumping::test_vietnam_8534_no_match
PASSED tests/test_landed_cost.py::TestAntiDumping::test_unknown_origin_no_match
PASSED tests/test_landed_cost.py::TestSkuCosts::test_lmw_true_no_duty_no_tax
PASSED tests/test_landed_cost.py::TestSkuCosts::test_lmw_false_duty_calculated
PASSED tests/test_landed_cost.py::TestSkuCosts::test_sales_tax_compounds_on_cif_plus_duties
PASSED tests/test_landed_cost.py::TestSkuCosts::test_freight_apportioned_by_weight
PASSED tests/test_landed_cost.py::TestSkuCosts::test_insurance_apportioned_by_value
PASSED tests/test_landed_cost.py::TestSkuCosts::test_add_triggered_for_china_8541
PASSED tests/test_landed_cost.py::TestSkuCosts::test_freight_fallback_to_value_when_weight_zero
12 passed
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test(module-c): unit tests for landed cost calculation math"
```

---

## Task 4: Add the API route

**Files:**
- Modify: `backend/api/routes.py`

- [ ] **Step 1: Append the Module C route at the end of `backend/api/routes.py`**

```python
# Module C — Landed Cost Calculation
@router.post("/api/calculate-landed-cost/{shipment_id}")
async def calculate_landed_cost_endpoint(shipment_id: str, request: Request):
    try:
        from calculator.landed_cost import calculate_landed_cost
        supabase = request.app.state.supabase
        result = await calculate_landed_cost(shipment_id, supabase)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"status": "ok", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 2: Commit**

```bash
git add backend/api/routes.py
git commit -m "feat(module-c): add POST /api/calculate-landed-cost/{shipment_id}"
```

---

## Task 5: Add `runModuleC` to `js/api.js`

**Files:**
- Modify: `js/api.js`

- [ ] **Step 1: Add `runModuleC` after `runModuleB` in `js/api.js`**

```javascript
/* ── Module C — Landed Cost ───────────────────────────────────── */
async function runModuleC(shipmentId) {
  return apiFetch(`/api/calculate-landed-cost/${shipmentId}`, 'POST')
}
```

- [ ] **Step 2: Commit**

```bash
git add js/api.js
git commit -m "feat(module-c): add runModuleC API helper"
```

---

## Task 6: Update `index.html` — badge ID, Run C buttons, pipeline count

**Files:**
- Modify: `index.html`

Three targeted changes:

**Change 1 — Add `id="modCBadge"` to the Module C status badge**

Find (around line 599):
```html
<span class="mod-status-badge" style="background:rgba(217,119,6,.10);color:#d97706">
  ⬅ Build This
</span>
```
Replace with:
```html
<span class="mod-status-badge" id="modCBadge" style="background:rgba(217,119,6,.10);color:#d97706">
  ⬅ Build This
</span>
```

**Change 2 — Update the Module C sub-title and add a `mod-footer` with Run button**

Find (around line 597):
```html
<div class="mod-sub">Teammate C — your module to build</div>
```
Replace with:
```html
<div class="mod-sub">CIF · LMW · ADD · Sales Tax · Processing Fee</div>
```

Then find the closing `</div><!-- /analysis-card mod-c -->` tag (the `</div>` that closes `<div class="analysis-card mod-c">`). It comes right after `</div><!-- mod-body -->`:
```html
              </div>
            </div>

          </div><!-- /analysis-grid -->
```
Replace with:
```html
              </div>
              <div class="mod-footer">
                <button class="btn" style="flex:1;justify-content:center" id="btnRunC2" onclick="triggerC()">
                  <i class="ti ti-calculator"></i> Run Module C
                </button>
              </div>
            </div>

          </div><!-- /analysis-grid -->
```

**Change 3 — Add "Run Module C" button in the ship-actions row and add `id="pipeCCount"` to pipeline banner**

Find (around line 529):
```html
              <button class="btn" id="btnRunB" onclick="triggerB()">
                <i class="ti ti-world"></i> Run Module B
              </button>
```
Replace with:
```html
              <button class="btn" id="btnRunB" onclick="triggerB()">
                <i class="ti ti-world"></i> Run Module B
              </button>
              <button class="btn" id="btnRunC" onclick="triggerC()">
                <i class="ti ti-calculator"></i> Run Module C
              </button>
```

Find the hardcoded Module C pipeline count (around line 682):
```html
              <div style="font-size:20px;font-weight:600;color:#d97706">0</div>
```
Replace with:
```html
              <div style="font-size:20px;font-weight:600;color:#d97706" id="pipeCCount">—</div>
```

- [ ] **Step 1: Make all four changes above to `index.html`**

- [ ] **Step 2: Commit**

```bash
git add index.html
git commit -m "feat(module-c): add Module C badge ID, Run C buttons, pipeline count ID"
```

---

## Task 7: Update `js/app.js` — Module C logic

**Files:**
- Modify: `js/app.js`

Five changes to `app.js`:

**Change 1 — Add `triggerC()` and `runSingleC()` after `runSingleB()`**

After the `runSingleB()` function (around line 433), add:

```javascript
async function triggerC() {
  const id = getActiveId()
  if (!id) { showToast('Search for a shipment first', true); return }
  await runSingleC(id)
}

async function runSingleC(shipmentId) {
  showToast(`⏳ Module C running for ${shipmentId}…`)
  const btns = ['btnRunC','btnRunC2'].map(i => $(i)).filter(Boolean)
  btns.forEach(b => { b.disabled = true; b.innerHTML = '<i class="ti ti-loader-2 spin"></i> Running…' })
  try {
    const r = await runModuleC(shipmentId)
    if (r.status === 'ok') {
      const d = r.data
      showToast(`✓ Module C — Landed USD ${money(d?.total_landed_usd)} | LMW=${d?.is_lmw_facility}`)
    } else {
      showToast('Module C failed: ' + (r.detail || 'unknown'), true)
    }
    await reloadCurrentShipment(shipmentId)
  } catch(e) { showToast('Module C error: ' + e.message, true) }
  finally {
    btns.forEach(b => { b.disabled = false; b.innerHTML = '<i class="ti ti-calculator"></i> Run Module C' })
  }
}
```

**Change 2 — Auto-chain Module C after Module B in `runSingleB()`**

Find inside `runSingleB()`:
```javascript
    await reloadCurrentShipment(shipmentId)
  } catch(e) { showToast('Module B error: ' + e.message, true) }
```
Replace with:
```javascript
    await reloadCurrentShipment(shipmentId)
    // Auto-chain: run Module C immediately after B succeeds
    await runSingleC(shipmentId)
  } catch(e) { showToast('Module B error: ' + e.message, true) }
```

**Change 3 — Update `renderShipmentResult()` to pass landed cost to Module C card**

Find:
```javascript
  // ── Module C Card ──
  renderModuleCCard(cls, fta, cif)
```
Replace with:
```javascript
  // ── Module C Card ──
  const lc = s.landed_costs?.[0] || null
  renderModuleCCard(cls, fta, cif, lc)
```

**Change 4 — Replace `renderModuleCCard()` with the full implementation**

Find and replace the entire `renderModuleCCard` function:

```javascript
/* ─── Module C card ──────────────────────────────────────────────── */
function renderModuleCCard(cls, fta, cif, lc) {
  const hs   = cls?.final_hs_code
  const rate = fta?.best_fta_rate_pct

  // Update status badge
  const badge = $('modCBadge')
  if (badge) {
    if (lc) {
      badge.textContent = '✓ Complete'
      badge.style.cssText = 'background:rgba(93,184,166,.12);color:var(--teal)'
    } else {
      badge.textContent = '⬅ Build This'
      badge.style.cssText = 'background:rgba(217,119,6,.10);color:#d97706'
    }
  }

  if (!lc) {
    // No Module C result yet — just show the inputs from A/B
    setHtml('mcHS',   hs   ? `<span style="font-family:var(--mono);color:var(--teal)">${hs}</span>`
                           : `<span style="color:var(--muted-soft)">⬆ run Module A</span>`)
    setHtml('mcRate', rate != null
      ? `<span style="font-family:var(--mono);color:var(--teal)">${rate}% (${fta.best_fta_name})</span>`
      : `<span style="color:var(--muted-soft)">⬆ run Module B</span>`)
    setHtml('mcCIF',  `<span style="font-family:var(--mono)">USD ${cif.toLocaleString()}</span>`)
    setHtml('mcTotal', `<span style="color:#d97706">Awaiting Module C</span>`)
    return
  }

  // Module C has run — show full MYR/USD breakdown
  const breakdown    = lc.cost_breakdown || []
  const totalCifMyr  = breakdown.reduce((s, r) => s + (r.apportionment_metrics?.calculated_cif_myr      || 0), 0)
  const totalDutyMyr = breakdown.reduce((s, r) => s + (r.regulatory_charges_myr?.customs_duty_charged   || 0), 0)
  const totalAddMyr  = breakdown.reduce((s, r) => s + (r.regulatory_charges_myr?.anti_dumping_duty_charged || 0), 0)
  const totalTaxMyr  = breakdown.reduce((s, r) => s + (r.regulatory_charges_myr?.sales_tax_charged      || 0), 0)
  const fxEst        = totalCifMyr > 0 && lc.cif_value_usd > 0 ? totalCifMyr / lc.cif_value_usd : 4.67
  const processingMyr = Math.round((lc.other_fees_usd || 0) * fxEst * 100) / 100
  const isLmw        = breakdown[0]?.flags_applied?.is_lmw_facility ?? true
  const hasAdd       = breakdown.some(r => r.flags_applied?.anti_dumping_matched)
  const fmt          = n => n.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})

  setHtml('modCBody', `
    <div style="font-size:11.5px;color:var(--muted-soft);margin-bottom:10px">
      Malaysian RMCD landed cost breakdown
    </div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px">
      ${isLmw ? `<span style="padding:3px 10px;border-radius:9999px;background:rgba(93,184,166,.1);color:var(--teal);font-size:11px;font-weight:600">✓ LMW Exempt</span>` : ''}
      ${hasAdd ? `<span style="padding:3px 10px;border-radius:9999px;background:rgba(232,165,90,.1);color:var(--amber);font-size:11px;font-weight:600">⚠ ADD Applied</span>` : ''}
    </div>
    <div class="formula-row">
      <span class="formula-lbl">HS Code <em style="font-style:normal;color:var(--teal);font-size:10px">(from A)</em></span>
      <span class="formula-val"><span style="font-family:var(--mono);color:var(--teal)">${hs || '—'}</span></span>
    </div>
    <div class="formula-row">
      <span class="formula-lbl">FTA Rate <em style="font-style:normal;color:var(--teal);font-size:10px">(from B)</em></span>
      <span class="formula-val"><span style="font-family:var(--mono);color:var(--teal)">${rate ?? '—'}% (${fta?.best_fta_name || '—'})</span></span>
    </div>
    <div style="border-top:1px solid var(--hairline);margin:10px 0"></div>
    <div class="formula-row">
      <span class="formula-lbl">Total CIF (MYR)</span>
      <span class="formula-val"><span style="font-family:var(--mono)">MYR ${fmt(totalCifMyr)}</span></span>
    </div>
    <div class="formula-row">
      <span class="formula-lbl">Customs Duty</span>
      <span class="formula-val" style="color:${totalDutyMyr === 0 ? 'var(--teal)' : 'var(--ink)'}">
        <span style="font-family:var(--mono)">MYR ${fmt(totalDutyMyr)}</span>
      </span>
    </div>
    ${totalAddMyr > 0 ? `
    <div class="formula-row">
      <span class="formula-lbl">Anti-Dumping Duty</span>
      <span class="formula-val" style="color:var(--amber)"><span style="font-family:var(--mono)">MYR ${fmt(totalAddMyr)}</span></span>
    </div>` : ''}
    <div class="formula-row">
      <span class="formula-lbl">Sales Tax (10%)</span>
      <span class="formula-val" style="color:${totalTaxMyr === 0 ? 'var(--teal)' : 'var(--ink)'}">
        <span style="font-family:var(--mono)">MYR ${fmt(totalTaxMyr)}</span>
      </span>
    </div>
    <div class="formula-row">
      <span class="formula-lbl">Processing Fee</span>
      <span class="formula-val"><span style="font-family:var(--mono)">MYR ${fmt(processingMyr)}</span></span>
    </div>
    <div class="formula-total" style="margin-top:14px">
      <span class="formula-total-lbl"><i class="ti ti-calculator" style="margin-right:4px"></i>Total Landed Cost</span>
      <span class="formula-total-val" id="mcTotal" style="color:var(--teal)">
        USD ${fmt(lc.total_landed_cost_usd || 0)}
      </span>
    </div>
    ${(lc.fta_saving_usd || 0) > 0 ? `
    <div style="margin-top:8px;text-align:center;font-size:11px;color:var(--teal);font-weight:600">
      ↓ FTA saves USD ${fmt(lc.fta_saving_usd)} vs MFN scenario
    </div>` : ''}
  `)
}
```

**Change 5 — Update `updatePipelineCounts()` and `renderTable()` for Module C**

Find `updatePipelineCounts()`:
```javascript
function updatePipelineCounts() {
  const total = SHIPMENTS.length
  const wA = SHIPMENTS.filter(s => s.hs_classifications?.length > 0).length
  const wB = SHIPMENTS.filter(s => s.fta_results?.length > 0).length
  setText('pipeACount', `${wA}/${total}`)
  setText('pipeBCount', `${wB}/${total}`)
  setText('batchMeta',  `${total} shipments · ${wA} classified · ${wB} FTA matched`)
  setText('tableCountMeta', `${total} total`)
}
```
Replace with:
```javascript
function updatePipelineCounts() {
  const total = SHIPMENTS.length
  const wA = SHIPMENTS.filter(s => s.hs_classifications?.length > 0).length
  const wB = SHIPMENTS.filter(s => s.fta_results?.length > 0).length
  const wC = SHIPMENTS.filter(s => s.landed_costs?.length > 0).length
  setText('pipeACount', `${wA}/${total}`)
  setText('pipeBCount', `${wB}/${total}`)
  setText('pipeCCount', `${wC}/${total}`)
  setText('batchMeta',  `${total} shipments · ${wA} classified · ${wB} FTA matched · ${wC} landed`)
  setText('tableCountMeta', `${total} total`)
}
```

Find `pDot(false,'C')` inside the `renderTable()` function:
```javascript
            ${pDot(false,'C')}
```
Replace with (add `const lc = s.landed_costs?.[0] || {}` before the return and use it):

Find the line in `renderTable()` that reads:
```javascript
    const cls = s.hs_classifications?.[0] || {}
    const fta = s.fta_results?.[0]        || {}
    const hasA = !!cls.final_hs_code
    const hasB = !!fta.best_fta_name
```
Replace with:
```javascript
    const cls  = s.hs_classifications?.[0] || {}
    const fta  = s.fta_results?.[0]        || {}
    const lc   = s.landed_costs?.[0]       || {}
    const hasA = !!cls.final_hs_code
    const hasB = !!fta.best_fta_name
    const hasC = !!lc.total_landed_cost_usd
```

Then find `${pDot(false,'C')}` and replace with `${pDot(hasC,'C')}`.

Also update `doBulk()` to include Module C:

Find:
```javascript
    if (!hasA) await runSingleA(s.sap_shipment_id).catch(()=>{})
    await runSingleB(s.sap_shipment_id).catch(()=>{})
```
Replace with:
```javascript
    if (!hasA) await runSingleA(s.sap_shipment_id).catch(()=>{})
    await runSingleB(s.sap_shipment_id).catch(()=>{})
    await runSingleC(s.sap_shipment_id).catch(()=>{})
```

- [ ] **Step 1: Make all five changes above to `js/app.js`**

- [ ] **Step 2: Commit**

```bash
git add js/app.js
git commit -m "feat(module-c): wire triggerC, renderModuleCCard, pipeline count, auto-chain after B"
```

---

## Task 8: End-to-end test

- [ ] **Step 1: Start the backend**

```bash
cd backend
uvicorn main:app --reload
```

Expected: `INFO: Application startup complete.`

- [ ] **Step 2: Open the frontend**

Open `index.html` in a browser (via Live Server in VS Code, or a local HTTP server).

- [ ] **Step 3: Seed the database**

Click **"Re-Seed Data"** in the sidebar. Toast should show:
```
✓ Seed done — 5 shipments, 5 classifications loaded
```

- [ ] **Step 4: Run the full pipeline for SHIP001**

1. Type `SHIP001` in the search box → click **Analyze**
2. Click **Run Module A** → toast: `✓ Module A — 8534.00 · 94% confidence`
3. Click **Run Module B** → toast: `✓ Module B — ATIGA @ 0% · saved $XXX`
   - Module C should auto-run immediately after → toast: `✓ Module C — Landed USD XXXX.XX | LMW=True`

- [ ] **Step 5: Verify Module C card**

The Module C card should show:
- Badge: `✓ Complete` in teal
- `✓ LMW Exempt` chip (green)
- MYR breakdown: Customs Duty = `MYR 0.00`, Sales Tax = `MYR 0.00`
- Processing Fee: `MYR 485.00` (50 + 300 + 2.5×(40×0.8 + 200×0.02) + 120 + 15 = 50+300+2.5×36+120+15 = 50+300+90+120+15 = 575.00)
- Total Landed Cost: `USD XXXX.XX`

- [ ] **Step 6: Verify pipeline banner**

In the All Shipments view, the Module C count should read `1/5`.

- [ ] **Step 7: Test the LMW toggle scenario (optional demo prep)**

In Supabase dashboard → `config` table → change `is_lmw_facility` to `false`.
Re-run Module C for SHIP001. The card should now show:
- No LMW Exempt chip
- Customs Duty: non-zero (ATIGA 0% so still $0)
- Run for SHIP002 (China, MFN 5%) to see non-zero duty + 10% sales tax

- [ ] **Step 8: Push to remote**

```bash
git push origin feature/layer3-landed-cost
```

---

## Self-Review

**Spec coverage check:**
- ✅ Step 1 (CIF apportionment by weight/value) — Task 2
- ✅ Step 2 (LMW eligibility) — Task 2
- ✅ Step 3 (Anti-Dumping Duty lookup) — Task 2
- ✅ Step 4 (Sales Tax 10% compounding) — Task 2
- ✅ Shipment-level consolidation — Task 2
- ✅ Processing fee breakdown (RMCD K1 + clearance + handling + terminal + EDI) — Task 2
- ✅ Config table seeding — Task 1
- ✅ bom_items quantity/weight seed update — Task 1
- ✅ POST /api/calculate-landed-cost/{id} — Task 4
- ✅ Auto-trigger after Module B — Task 7, Change 2
- ✅ Module C card status badge — Task 6 + Task 7
- ✅ LMW chip, ADD chip display — Task 7, Change 4
- ✅ MYR breakdown (CIF, duty, ADD, tax, processing, total) — Task 7, Change 4
- ✅ USD total in card — Task 7, Change 4
- ✅ FTA saving display — Task 7, Change 4
- ✅ Pipeline count (C/total) — Task 6 + Task 7, Change 5
- ✅ Table dot for C — Task 7, Change 5
- ✅ Bulk run includes C — Task 7, Change 5
- ✅ Precision: round(val, 4) throughout — Task 2
- ✅ Fallback when total_weight_kg = 0 — Task 2
- ✅ Error when Module B not run — Task 2

**Missing from spec that are intentionally deferred:**
- `anti_dumping_orders` Supabase table — hardcoded dict in `landed_cost.py` is sufficient for POC
- `supplier_rvc_pct` field not in schema.sql but exists in seed — no change needed, Module C doesn't use it
