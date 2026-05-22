#  module b (fta_matcher)
from supabase import Client 

# mock data for module b tetsing only, 
# to do without mocdule A 
MOCK_CLASSIFICATIONS = {
    "SHIP001": {"final_hs_code": "8534.00", "confidence_score": 94},
    "SHIP002": {"final_hs_code": "8501.52", "confidence_score": 89},
    "SHIP003": {"final_hs_code": "7604.29", "confidence_score": 96},
    "SHIP004": {"final_hs_code": "8542.31", "confidence_score": 82},
    "SHIP005": {"final_hs_code": "9001.90", "confidence_score": 95},
}

#  get the HS code form the fta_results form module A 
def get_hs_code(sap_shipment_id:str,shipment_uuid:str,supabase:Client) -> dict:
    result = supabase.table("hs_classifications").select("final_hs_code,confidence_score,module_a_status").eq("shipment_id",shipment_uuid).execute()

    if result.data:
        # real module A data exists then use it 
        return result.data[0]

    # if no, then fallback to the mock data just now 
    mock = MOCK_CLASSIFICATIONS.get(sap_shipment_id)
    if mock:
        print(f"[fta_matcher] Using mock classification for {sap_shipment_id}")
        return{
            "final_hs_code":mock["final_hs_code"],
            "confidence_score":mock["confidence_score"],
            "module_a_status":  "auto_passed"
        }
    
    return None

#  step 2 - find which fta include the country of origin 
def get_candidate_ftas(origin_country:str,supabase:Client) -> list:
    result = supabase.table("fta_coverage").select(
        "fta_name, member_countries"
    ).execute() 

    candidates = []

    for row in result.data:
        members = row.get("member_countries") or []

        if origin_country in members:
            candidates.append(row["fta_name"])
        
    return candidates 
    # fta candidates or country candidates 

# step 3 - check if fta qualified based on ROO rules 
def check_one_fta(fta_name: str, hs_code: str,origin_country: str, supplier_rvc: float, supabase: Client) -> dict:
    rate_result = supabase.table("fta_rates").select("preferential_rate_pct").eq("fta_name", fta_name).eq("hs_code", hs_code).eq("origin_country", origin_country).execute()
        #  condition 

    if not rate_result.data:
        return {"fta_name": fta_name, "qualifies": False, "reason": "No rate found"}
    
    rate = rate_result.data[0]["preferential_rate_pct"]
    
    # get ROO rules 
    roo_result = supabase.table("roo_rules").select(
        "roo_type, rvc_threshold_pct, tariff_shift_description"
        ).eq("fta_name", fta_name).eq("hs_code", hs_code).execute()

    if not roo_result.data:
    return {"fta_name": fta_name, "qualifies": False, "reason": "No RoO rule found"}

    roo = roo_result.data[0]
    roo_type = roo["roo_type"]

    # Check RoO based on type
    if roo_type == "RVC":
        threshold = roo["rvc_threshold_pct"]
        passed = supplier_rvc >= threshold
        return {
            "fta_name":   fta_name,
            "qualifies":  passed,
            "rate":       rate,
            "roo_type":   roo_type,
            "threshold":  threshold,
            "rvc_declared": supplier_rvc,
            "reason":     f"RVC {supplier_rvc}% {'≥' if passed else '<'} threshold {threshold}%"
        }

    elif roo_type == "tariff_shift":
    # Tariff shift,  for POC we assume it passes if rule exists
    return {
        "fta_name":  fta_name,
        "qualifies": True,
        "rate":      rate,
        "roo_type":  roo_type,
        "threshold": 0,
        "rvc_declared": 0,
        "reason":    f"Tariff shift rule met: {roo['tariff_shift_description']}"
    }

    elif roo_type == "wholly_obtained":
    # For POC — flag as conditional, analyst reviews
    return {
    "fta_name":  fta_name,
    "qualifies": False,
    "rate":      rate,
    "roo_type":  roo_type,
    "reason":    "Wholly obtained rule requires analyst verification. "
                    "Electronics rarely qualify. Analyst must confirm."
    }

    return {"fta_name": fta_name, "qualifies": False, "reason": "Unknown RoO type"}

#  main function 
async def match_fta(shipment_id: str, supabase: Client) -> dict:
    try:
        # Get shipment data
        ship_result = supabase.table("shipments").select(
            "id, sap_shipment_id, origin_country, supplier_rvc_pct, "
            "shipment_value_usd, freight_cost_usd, insurance_cost_usd"
        ).eq("sap_shipment_id", shipment_id).execute()

        if not ship_result.data:
            return {"error": f"Shipment {shipment_id} not found"}

        ship = ship_result.data[0]
        origin       = ship["origin_country"]
        supplier_rvc = ship["supplier_rvc_pct"] or 0
        cif_value    = (ship["shipment_value_usd"] +
                        ship["freight_cost_usd"] +
                        ship["insurance_cost_usd"])

        # get the HS code
        classification = get_hs_code(
            ship["sap_shipment_id"], ship["id"], supabase
        )
        if not classification:
            return {"error": f"No HS classification found for {shipment_id}"}

        hs_code = classification["final_hs_code"]

        # Get MFN rate , fallback if no fta matches 
        mfn_result = supabase.table("tariff_rates").select(
            "mfn_rate_pct"
        ).eq("hs_code", hs_code).execute()
        mfn_rate = mfn_result.data[0]["mfn_rate_pct"] if mfn_result.data else 5.0

        # Find candidate FTAs for origin country
        candidates = get_candidate_ftas(origin, supabase)
        print(f"[fta_matcher] {shipment_id} | origin={origin} | "
              f"HS={hs_code} | candidates={candidates}")

        # Check each FTA
        all_checked  = []
        qualifying   = []

        for fta_name in candidates:
            result = check_one_fta(
                fta_name, hs_code, origin, supplier_rvc, supabase
            )
            all_checked.append(result)
            if result.get("qualifies"):
                qualifying.append(result)
                print(f"[fta_matcher]   ✓ {fta_name} qualifies — rate {result['rate']}%")
            else:
                print(f"[fta_matcher]   ✗ {fta_name} failed — {result['reason']}")

        # Pick best FTA (lowest rate)
        if qualifying:
            best = min(qualifying, key=lambda x: x["rate"])
            fta_rate      = best["rate"]
            best_fta_name = best["fta_name"]
            roo_type      = best["roo_type"]
            roo_passed    = True
            rvc_threshold = best.get("threshold", 0)
            module_status = "fta_applied"
        else:
            # No FTA qualifies → use MFN
            fta_rate      = mfn_rate
            best_fta_name = "MFN"
            roo_type      = None
            roo_passed    = False
            rvc_threshold = 0
            module_status = "mfn_applied" if candidates else "no_fta_available"

        # Calculate duty saving
        mfn_duty   = (mfn_rate / 100) * cif_value
        fta_duty   = (fta_rate / 100) * cif_value
        duty_saving = round(mfn_duty - fta_duty, 2)

        # Save to fta_results
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
            "module_b_status":       module_status
        }).execute()

        print(f"[fta_matcher] ✓ {shipment_id} → {best_fta_name} "
              f"({fta_rate}%) | saving=${duty_saving}")

        return {
            "shipment_id":    shipment_id,
            "hs_code":        hs_code,
            "origin":         origin,
            "best_fta":       best_fta_name,
            "fta_rate_pct":   fta_rate,
            "mfn_rate_pct":   mfn_rate,
            "duty_saving_usd": duty_saving,
            "status":         module_status
        }

    except Exception as e:
        print(f"[fta_matcher] ✗ {shipment_id} failed: {e}")
        return {"error": str(e)}
