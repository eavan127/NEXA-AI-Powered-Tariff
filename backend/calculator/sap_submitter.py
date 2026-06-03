# backend/calculator/sap_submitter.py
from supabase import Client
from ingestion.sap_connector import submit_to_sap
import datetime


async def submit_shipment_to_sap(shipment_id: str, supabase: Client) -> dict:
    # 1. Load shipment + all module results
    ship = supabase.table("shipments").select(
        "*, hs_classifications(*), fta_results(*), landed_costs(*)"
    ).eq("sap_shipment_id", shipment_id).single().execute()
    if not ship.data:
        return {"error": f"Shipment {shipment_id} not found"}
    s = ship.data
    if s["status"] != "approved":
        return {"error": f"Shipment {shipment_id} is not approved (status={s['status']})"}
    cls = (s.get("hs_classifications") or [{}])[0]
    fta = (s.get("fta_results")        or [{}])[0]
    lc  = (s.get("landed_costs")       or [{}])[0]
    # 2. Build SAP payload
    payload = {
        "SAPShipmentId":    shipment_id,
        "FinalHSCode":      cls.get("final_hs_code"),
        "BestFTAName":      fta.get("best_fta_name"),
        "FTARatePct":       fta.get("best_fta_rate_pct"),
        "DutySavingUSD":    fta.get("duty_saving_usd"),
        "TotalLandedUSD":   lc.get("total_landed_cost_usd"),
        "FTASavingUSD":     lc.get("fta_saving_usd"),
        "AnalystApproved":  True,
        "SubmittedAt":      datetime.datetime.utcnow().isoformat() + "Z",
    }
    # 3. Call SAP
    result = await submit_to_sap(shipment_id, payload)
    sap_doc_id   = result.get("sap_document_id")
    submitted_at = result.get("submitted_at")
    # 4. Update shipments table
    supabase.table("shipments").update({
        "status":              "submitted",
        "submitted_to_sap_at": submitted_at,
        "sap_document_id":     sap_doc_id,
    }).eq("sap_shipment_id", shipment_id).execute()
    # 5. Write to audit_trail
    supabase.table("audit_trail").insert({
        "shipment_id":  s["id"],
        "event_type":   "sap_submission",
        "analyst_note": f"{shipment_id} submitted to SAP. Doc ID: {sap_doc_id}",
    }).execute()
    return {
        "shipment_id":     shipment_id,
        "sap_document_id": sap_doc_id,
        "submitted_at":    submitted_at,
        "status":          "submitted",
    }


async def submit_batch_to_sap(shipment_ids: list[str], supabase: Client) -> dict:
    """Submit a batch of approved shipments."""
    results, errors = [], []
    for sid in shipment_ids:
        r = await submit_shipment_to_sap(sid, supabase)
        if "error" in r:
            errors.append({"shipment_id": sid, "error": r["error"]})
        else:
            results.append(r)
    return {"submitted": results, "errors": errors}

    