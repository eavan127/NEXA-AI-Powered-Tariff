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
