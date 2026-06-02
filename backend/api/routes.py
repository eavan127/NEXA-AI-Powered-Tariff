from fastapi import APIRouter, HTTPException, Request
from api.schemas import ProcessBatchRequest, ApproveRequest, RejectRequest, OverrideHSRequest
from classifier.hs_classifier import classify_hs_code

router = APIRouter()


def _sort_nested(rows: list) -> list:
    """Sort hs_classifications / fta_results / landed_costs by created_at desc
    so that index [0] is always the most recent record."""
    for row in rows:
        for field in ("hs_classifications", "fta_results", "landed_costs"):
            arr = row.get(field)
            if arr and isinstance(arr, list):
                arr.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return rows

# seed data 
@router.post("/api/seed")
async def seed_data(request:Request):
    try :
        from seed_database import run_seed
        result = await run_seed()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise  HTTPException(status_code=500,detail=str(e))

# shipments 
@router.get("/api/shipments")
async def get_shipments(request: Request, status: str = "all"):
    try:
        supabase = request.app.state.supabase
        query = supabase.table("shipments").select(
            "*, hs_classifications(*), fta_results(*), landed_costs(*)"
        )
        if status != "all":
            # just a statement to make it true 
            query = query.eq("status", status)
        result = query.order("created_at", desc=True).execute()
        _sort_nested(result.data)
        return {"status": "ok", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/shipments/{shipment_id}")
async def get_shipment_detail(shipment_id: str, request: Request):
    try:
        supabase = request.app.state.supabase
        result = supabase.table("shipments").select(
            "*, hs_classifications(*), fta_results(*), landed_costs(*)"
        ).eq("sap_shipment_id", shipment_id).execute()
        # eq mean equal(where sap_shipment_id is equal to the shipment_id)

        if not result.data:
            raise HTTPException(status_code=404, detail="Shipment not found")

        _sort_nested(result.data)

        audit = supabase.table("audit_trail").select("*").eq(
            "shipment_id", result.data[0]["id"]
        ).order("created_at", desc=True).execute()

        return {
            "status": "ok",
            "data": result.data[0],
            "audit_trail": audit.data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# reports 
@router.get("/api/reports/summary")
async def get_summary(request: Request):
    try:
        supabase = request.app.state.supabase

        shipments = supabase.table("shipments").select("status").execute()
        total = len(shipments.data)
        approved = len([s for s in shipments.data if s["status"] == "approved"])
        flagged = len([s for s in shipments.data if s["status"] == "flagged"])
        pending = len([s for s in shipments.data if s["status"] == "pending"])

        savings = supabase.table("fta_results").select("duty_saving_usd").execute()
        total_saving = sum(
            s["duty_saving_usd"] for s in savings.data
            # take the value only from the the list
            #[
            #     {"duty_saving_usd": 460.04},
            #     {"duty_saving_usd": 212.50},
            #     {"duty_saving_usd": None},    ← some shipments have no FTA saving yet
            #     {"duty_saving_usd": 89.20},
            # ]

            if s["duty_saving_usd"] is not None
        )

        return {
            "status": "ok",
            "total_shipments": total,
            "approved": approved,
            "flagged": flagged,
            "pending": pending,
            "total_fta_saving_usd": round(total_saving, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Module A — HS Code Classification
@router.post("/api/classify/{shipment_id}")
async def classify_shipment(shipment_id: str, request: Request):
    try:
        supabase = request.app.state.supabase
        result = classify_hs_code(shipment_id, supabase)
        return {
            "status": "ok",
            "shipment_id": shipment_id,
            "classification": result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
@router.post("/api/match-fta/{shipment_id}")
async def match_fta_endpoint(shipment_id: str, request: Request):
    try:
        from calculator.fta_matcher import match_fta
        supabase = request.app.state.supabase
        result = await match_fta(shipment_id, supabase)
        return {"status": "ok", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Approve / Flag ────────────────────────────────────────────────

@router.post("/api/shipments/{shipment_id}/approve")
async def approve_shipment(shipment_id: str, request: Request):
    try:
        supabase = request.app.state.supabase
        ship = supabase.table("shipments").select("id") \
            .eq("sap_shipment_id", shipment_id).single().execute()
        if not ship.data:
            raise HTTPException(status_code=404, detail="Shipment not found")
        supabase.table("shipments").update({"status": "approved"}) \
            .eq("sap_shipment_id", shipment_id).execute()
        supabase.table("audit_trail").insert({
            "shipment_id": ship.data["id"],
            "action": f"{shipment_id} approved by analyst Sarah Lim via NEXA UI"
        }).execute()
        return {"status": "ok", "message": f"{shipment_id} approved"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/shipments/{shipment_id}/flag")
async def flag_shipment(shipment_id: str, request: Request):
    try:
        supabase = request.app.state.supabase
        ship = supabase.table("shipments").select("id") \
            .eq("sap_shipment_id", shipment_id).single().execute()
        if not ship.data:
            raise HTTPException(status_code=404, detail="Shipment not found")
        supabase.table("shipments").update({"status": "flagged"}) \
            .eq("sap_shipment_id", shipment_id).execute()
        supabase.table("audit_trail").insert({
            "shipment_id": ship.data["id"],
            "action": f"{shipment_id} flagged for analyst review via NEXA UI"
        }).execute()
        return {"status": "ok", "message": f"{shipment_id} flagged"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── FTA Library ───────────────────────────────────────────────────

@router.get("/api/fta-coverage")
async def get_fta_coverage(request: Request):
    try:
        supabase = request.app.state.supabase
        result = supabase.table("fta_coverage").select("*").execute()
        return {"status": "ok", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/fta-rates")
async def get_fta_rates_list(
    request: Request,
    hs_code: str = None,
    fta_name: str = None
):
    try:
        supabase = request.app.state.supabase
        query = supabase.table("fta_rates").select("*") \
            .not_.is_("origin_country", "null") \
            .lte("preferential_rate_pct", 100)
        if hs_code:
            query = query.ilike("hs_code", f"{hs_code}%")
        if fta_name:
            query = query.eq("fta_name", fta_name)
        result = query.order("preferential_rate_pct").limit(200).execute()
        return {"status": "ok", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Audit Trail ───────────────────────────────────────────────────

@router.get("/api/audit-trail")
async def get_all_audit_trail(request: Request):
    try:
        supabase = request.app.state.supabase
        result = supabase.table("audit_trail").select("*") \
            .order("created_at", desc=True).limit(500).execute()
        return {"status": "ok", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# Human Validation — HS Code Override
@router.post("/api/shipments/{shipment_id}/override-hs")
async def override_hs_code(shipment_id: str, request: Request):
    try:
        body      = await request.json()
        hs_code   = (body.get("hs_code")  or "").strip()
        reason    = (body.get("reason")   or "").strip()
        if not hs_code or not reason:
            raise HTTPException(status_code=400, detail="hs_code and reason are required")

        supabase = request.app.state.supabase

        ship = supabase.table("shipments").select("id") \
            .eq("sap_shipment_id", shipment_id).single().execute()
        if not ship.data:
            raise HTTPException(status_code=404, detail="Shipment not found")

        # Update latest classification record
        cls_res = supabase.table("hs_classifications").select("id") \
            .eq("shipment_id", ship.data["id"]) \
            .order("created_at", desc=True).limit(1).execute()
        if cls_res.data:
            supabase.table("hs_classifications").update({
                "analyst_override_hs": hs_code,
                "final_hs_code":       hs_code,
            }).eq("id", cls_res.data[0]["id"]).execute()
        else:
            supabase.table("hs_classifications").insert({
                "shipment_id":        ship.data["id"],
                "analyst_override_hs": hs_code,
                "final_hs_code":       hs_code,
                "module_a_status":    "auto_passed",
            }).execute()

        supabase.table("shipments").update({"status": "approved"}) \
            .eq("sap_shipment_id", shipment_id).execute()

        supabase.table("audit_trail").insert({
            "shipment_id": ship.data["id"],
            "action": f"{shipment_id} HS code overridden to {hs_code} by analyst. Reason: {reason}"
        }).execute()

        return {"status": "ok", "message": f"HS overridden to {hs_code}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Human Validation — Escalate
@router.post("/api/shipments/{shipment_id}/escalate")
async def escalate_shipment(shipment_id: str, request: Request):
    try:
        body     = await request.json()
        assignee = (body.get("assignee") or "Senior Analyst").strip()
        notes    = (body.get("notes")    or "").strip()
        if not notes:
            raise HTTPException(status_code=400, detail="notes are required")

        supabase = request.app.state.supabase

        ship = supabase.table("shipments").select("id") \
            .eq("sap_shipment_id", shipment_id).single().execute()
        if not ship.data:
            raise HTTPException(status_code=404, detail="Shipment not found")

        supabase.table("shipments").update({"status": "flagged"}) \
            .eq("sap_shipment_id", shipment_id).execute()

        supabase.table("audit_trail").insert({
            "shipment_id": ship.data["id"],
            "action": f"{shipment_id} escalated to {assignee}. Notes: {notes}"
        }).execute()

        return {"status": "ok", "message": f"Escalated to {assignee}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
