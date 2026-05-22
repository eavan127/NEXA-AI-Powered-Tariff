from fastapi import APIRouter, HTTPException, Request
from api.schemas import ProcessBatchRequest, ApproveRequest, RejectRequest, OverrideHSRequest
from classifier.hs_classifier import classify_hs_code

router = APIRouter()

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))