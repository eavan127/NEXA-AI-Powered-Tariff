from supabase import Client

# ── Multi-FTA lookup matrix ───────────────────────────────────────
# When a shipment arrives from one of these countries, ALL listed FTAs
# are checked and the one giving the lowest passing rate is used.
MULTI_FTA_MAP: dict[str, list[str]] = {
    "China":         ["ACFTA", "RCEP"],
    "Japan":         ["AJCEP", "MJEPA", "RCEP", "CPTPP"],
    "South Korea":   ["AKFTA", "RCEP"],
    "Australia":     ["MAFTA", "AANZFTA", "RCEP", "CPTPP"],
    "New Zealand":   ["MNZFTA", "AANZFTA", "RCEP", "CPTPP"],
    "Vietnam":       ["ATIGA", "RCEP", "CPTPP"],
    "Thailand":      ["ATIGA", "RCEP"],
    "Indonesia":     ["ATIGA", "RCEP"],
    "Singapore":     ["ATIGA", "RCEP", "CPTPP"],
    "India":         ["AIFTA", "MICECA"],
    "Hong Kong":     ["AHKFTA"],
    "Pakistan":      ["MPCEPA", "TPS-OIC"],
    "Turkey":        ["MTFTA", "TPS-OIC"],
    "Chile":         ["MCFTA", "CPTPP"],
    "Canada":        ["CPTPP"],
    "Mexico":        ["CPTPP"],
    "Peru":          ["CPTPP"],
    "Brunei":        ["ATIGA", "RCEP", "CPTPP"],
    "Cambodia":      ["ATIGA", "RCEP"],
    "Laos":          ["ATIGA", "RCEP"],
    "Myanmar":       ["ATIGA", "RCEP"],
    "Philippines":   ["ATIGA", "RCEP"],
    "United Kingdom": ["CPTPP"],
}

# ── Mock classifications (Module A fallback) ──────────────────────
MOCK_CLASSIFICATIONS = {
    "SHIP001": {"final_hs_code": "8534.00", "confidence_score": 94},
    "SHIP002": {"final_hs_code": "8501.52", "confidence_score": 89},
    "SHIP003": {"final_hs_code": "7604.29", "confidence_score": 96},
    "SHIP004": {"final_hs_code": "8542.31", "confidence_score": 82},
    "SHIP005": {"final_hs_code": "9001.90", "confidence_score": 95},
}


# ── Step 1: get HS code from Module A ────────────────────────────
def get_hs_code(sap_shipment_id: str, shipment_uuid: str, supabase: Client) -> dict:
    result = supabase.table("hs_classifications").select(
        "final_hs_code,confidence_score,module_a_status"
    ).eq("shipment_id", shipment_uuid).execute()

    if result.data:
        return result.data[0]

    mock = MOCK_CLASSIFICATIONS.get(sap_shipment_id)
    if mock:
        print(f"[fta_matcher] Using mock classification for {sap_shipment_id}")
        return {
            "final_hs_code":    mock["final_hs_code"],
            "confidence_score": mock["confidence_score"],
            "module_a_status":  "auto_passed",
        }
    return None


# ── Step 2: find all FTAs applicable for origin country ──────────
def get_candidate_ftas(origin_country: str, supabase: Client) -> list[str]:
    # Primary: deterministic multi-FTA map (faster, no DB round-trip)
    if origin_country in MULTI_FTA_MAP:
        return MULTI_FTA_MAP[origin_country]

    # Fallback: scan fta_coverage member_countries in DB
    result = supabase.table("fta_coverage").select(
        "fta_name,member_countries"
    ).execute()
    return [
        row["fta_name"]
        for row in result.data
        if origin_country in (row.get("member_countries") or [])
    ]


# ── Step 3: check one FTA for RoO compliance and get rate ────────
def check_one_fta(
    fta_name: str,
    hs_code: str,
    origin_country: str,
    supplier_rvc: float,
    supabase: Client,
) -> dict:
    rate_result = (
        supabase.table("fta_rates")
        .select("preferential_rate_pct,rate_staging,staging_category,final_rate,final_year")
        .eq("fta_name", fta_name)
        .eq("hs_code", hs_code)
        .eq("origin_country", origin_country)
        .execute()
    )

    if not rate_result.data:
        return {"fta_name": fta_name, "qualifies": False, "reason": "No rate found"}

    row  = rate_result.data[0]
    rate = row["preferential_rate_pct"]

    roo_result = (
        supabase.table("roo_rules")
        .select("roo_type,rvc_threshold_pct,tariff_shift_description")
        .eq("fta_name", fta_name)
        .eq("hs_code", hs_code)
        .execute()
    )

    if not roo_result.data:
        return {"fta_name": fta_name, "qualifies": False, "reason": "No RoO rule found"}

    roo      = roo_result.data[0]
    roo_type = roo["roo_type"]

    # Rate staging context for display
    staging_info = {
        "rate_staging":     row.get("rate_staging"),
        "staging_category": row.get("staging_category"),
        "final_rate":       row.get("final_rate"),
        "final_year":       row.get("final_year"),
    }

    if roo_type == "RVC":
        threshold = roo["rvc_threshold_pct"]
        passed    = supplier_rvc >= threshold
        return {
            "fta_name":     fta_name,
            "qualifies":    passed,
            "rate":         rate,
            "roo_type":     roo_type,
            "threshold":    threshold,
            "rvc_declared": supplier_rvc,
            "reason": f"RVC {supplier_rvc}% {'≥' if passed else '<'} threshold {threshold}%",
            **staging_info,
        }

    if roo_type == "tariff_shift":
        return {
            "fta_name":     fta_name,
            "qualifies":    True,
            "rate":         rate,
            "roo_type":     roo_type,
            "threshold":    0,
            "rvc_declared": 0,
            "reason": f"Tariff shift rule met: {roo['tariff_shift_description']}",
            **staging_info,
        }

    if roo_type == "wholly_obtained":
        return {
            "fta_name":  fta_name,
            "qualifies": False,
            "rate":      rate,
            "roo_type":  roo_type,
            "reason":    "Wholly obtained rule — analyst verification required. "
                         "Electronics rarely qualify.",
            **staging_info,
        }

    return {"fta_name": fta_name, "qualifies": False, "reason": "Unknown RoO type"}


# ── Main: check all applicable FTAs, pick lowest qualifying rate ──
async def match_fta(shipment_id: str, supabase: Client) -> dict:
    try:
        ship_result = supabase.table("shipments").select(
            "id,sap_shipment_id,origin_country,supplier_rvc_pct,"
            "shipment_value_usd,freight_cost_usd,insurance_cost_usd"
        ).eq("sap_shipment_id", shipment_id).execute()

        if not ship_result.data:
            return {"error": f"Shipment {shipment_id} not found"}

        ship         = ship_result.data[0]
        origin       = ship["origin_country"]
        supplier_rvc = ship["supplier_rvc_pct"] or 0
        cif_value    = (
            ship["shipment_value_usd"] +
            ship["freight_cost_usd"] +
            ship["insurance_cost_usd"]
        )

        classification = get_hs_code(ship["sap_shipment_id"], ship["id"], supabase)
        if not classification:
            return {"error": f"No HS classification found for {shipment_id}"}

        hs_code = classification["final_hs_code"]

        mfn_result = supabase.table("tariff_rates").select(
            "mfn_rate_pct"
        ).eq("hs_code", hs_code).execute()
        mfn_rate = mfn_result.data[0]["mfn_rate_pct"] if mfn_result.data else 5.0

        # Check ALL applicable FTAs for this origin country
        candidates = get_candidate_ftas(origin, supabase)
        print(
            f"[fta_matcher] {shipment_id} | origin={origin} | "
            f"HS={hs_code} | candidates={candidates}"
        )

        all_checked = []
        qualifying  = []

        for fta_name in candidates:
            result = check_one_fta(fta_name, hs_code, origin, supplier_rvc, supabase)
            all_checked.append(result)
            if result.get("qualifies"):
                qualifying.append(result)
                print(f"[fta_matcher]   ✓ {fta_name} qualifies — {result['rate']}%")
            else:
                print(f"[fta_matcher]   ✗ {fta_name} — {result['reason']}")

        # Pick the FTA that gives the lowest rate
        if qualifying:
            best          = min(qualifying, key=lambda x: x["rate"])
            fta_rate      = best["rate"]
            best_fta_name = best["fta_name"]
            roo_type      = best["roo_type"]
            roo_passed    = True
            rvc_threshold = best.get("threshold", 0)
            module_status = "fta_applied"
        else:
            fta_rate      = mfn_rate
            best_fta_name = "MFN"
            roo_type      = None
            roo_passed    = False
            rvc_threshold = 0
            module_status = "mfn_applied" if candidates else "no_fta_available"

        mfn_duty    = (mfn_rate / 100) * cif_value
        fta_duty    = (fta_rate / 100) * cif_value
        duty_saving = round(mfn_duty - fta_duty, 2)

        supabase.table("fta_results").insert({
            "shipment_id":           ship["id"],
            "applicable_ftas":       all_checked,
            "best_fta_name":         best_fta_name,
            "best_fta_rate_pct":     fta_rate,
            "mfn_rate_pct":          mfn_rate,
            "roo_type":              roo_type,
            "roo_passed":            roo_passed,
            "rvc_supplier_declared": supplier_rvc,
            "rvc_threshold":         rvc_threshold,
            "duty_saving_usd":       duty_saving,
            "module_b_status":       module_status,
        }).execute()

        print(
            f"[fta_matcher] ✓ {shipment_id} → {best_fta_name} "
            f"({fta_rate}%) | saving=${duty_saving}"
        )

        return {
            "shipment_id":     shipment_id,
            "hs_code":         hs_code,
            "origin":          origin,
            "best_fta":        best_fta_name,
            "fta_rate_pct":    fta_rate,
            "mfn_rate_pct":    mfn_rate,
            "duty_saving_usd": duty_saving,
            "all_ftas_checked": len(all_checked),
            "status":          module_status,
        }

    except Exception as e:
        print(f"[fta_matcher] ✗ {shipment_id} failed: {e}")
        return {"error": str(e)}
