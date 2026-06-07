from fastapi import APIRouter, HTTPException, Request
from api.schemas import ProcessBatchRequest, ApproveRequest, RejectRequest, OverrideHSRequest, DryRunPdfRequest
from classifier.hs_classifier import classify_hs_code
from ingestion.sap_connector import write_duty_to_sap
from fastapi.responses import Response
from reports.compliance_pdf import generate_compliance_pdf

router = APIRouter()

ANALYST_ID   = "SARAH_LIM"
ANALYST_NAME = "Sarah Lim"


def _sort_nested(rows: list) -> list:
    """Sort hs_classifications / fta_results / landed_costs by created_at desc
    so that index [0] is always the most recent record."""
    for row in rows:
        for field in ("hs_classifications", "fta_results", "landed_costs"):
            arr = row.get(field)
            if arr and isinstance(arr, list):
                arr.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return rows


def _get_latest_cls(supabase, shipment_uuid: str) -> dict:
    """Helper — fetch latest hs_classification row for a shipment."""
    res = supabase.table("hs_classifications") \
        .select("id, ai_hs_code, final_hs_code, confidence_score, reasoning_text") \
        .eq("shipment_id", shipment_uuid) \
        .order("created_at", desc=True).limit(1).execute()
    return res.data[0] if res.data else {}


# ── Seed ──────────────────────────────────────────────────────────
@router.post("/api/seed")
async def seed_data(request: Request):
    try:
        from seed_database import run_seed
        result = await run_seed()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Shipments ─────────────────────────────────────────────────────
@router.get("/api/shipments")
async def get_shipments(request: Request, status: str = "all"):
    try:
        supabase = request.app.state.supabase
        query = supabase.table("shipments").select(
            "*, hs_classifications(*), fta_results(*), landed_costs(*)"
        )
        if status != "all":
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


# ── Summary ───────────────────────────────────────────────────────
@router.get("/api/reports/summary")
async def get_summary(request: Request):
    try:
        supabase = request.app.state.supabase

        shipments = supabase.table("shipments").select("status").execute()
        total    = len(shipments.data)
        approved = len([s for s in shipments.data if s["status"] == "approved"])
        flagged  = len([s for s in shipments.data if s["status"] == "flagged"])
        pending  = len([s for s in shipments.data if s["status"] == "pending"])

        savings = supabase.table("fta_results").select("duty_saving_usd").execute()
        total_saving = sum(
            s["duty_saving_usd"] for s in savings.data
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


# ── Module A — HS Classification ──────────────────────────────────
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


# ── Module B — FTA Match ──────────────────────────────────────────
@router.post("/api/match-fta/{shipment_id}")
async def match_fta_endpoint(shipment_id: str, request: Request):
    try:
        from calculator.fta_matcher import match_fta
        supabase = request.app.state.supabase
        result = await match_fta(shipment_id, supabase)
        return {"status": "ok", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Module C — Landed Cost ────────────────────────────────────────
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


# ── Approve ───────────────────────────────────────────────────────
@router.post("/api/shipments/{shipment_id}/approve")
async def approve_shipment(shipment_id: str, request: Request):
    try:
        supabase = request.app.state.supabase
        ship = supabase.table("shipments").select("id") \
            .eq("sap_shipment_id", shipment_id).single().execute()
        if not ship.data:
            raise HTTPException(status_code=404, detail="Shipment not found")

        cls = _get_latest_cls(supabase, ship.data["id"])

        supabase.table("shipments").update({"status": "approved"}) \
            .eq("sap_shipment_id", shipment_id).execute()

        supabase.table("audit_trail").insert({
            "shipment_id":      ship.data["id"],
            "event_type":       "analyst_decision",
            "analyst_id":       ANALYST_ID,
            "analyst_action":   "approved",
            "confidence_score": cls.get("confidence_score"),
            "reasoning_text":   cls.get("reasoning_text"),
            "analyst_note":     f"{shipment_id} approved by {ANALYST_NAME} via NEXA UI"
        }).execute()

        return {"status": "ok", "message": f"{shipment_id} approved"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Flag ──────────────────────────────────────────────────────────
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
            "shipment_id":    ship.data["id"],
            "event_type":     "analyst_decision",
            "analyst_id":     ANALYST_ID,
            "analyst_action": "flagged",
            "analyst_note":   f"{shipment_id} flagged for analyst review via NEXA UI"
        }).execute()

        return {"status": "ok", "message": f"{shipment_id} flagged"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Escalate ──────────────────────────────────────────────────────
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

        cls = _get_latest_cls(supabase, ship.data["id"])

        supabase.table("shipments").update({"status": "flagged"}) \
            .eq("sap_shipment_id", shipment_id).execute()

        supabase.table("audit_trail").insert({
            "shipment_id":      ship.data["id"],
            "event_type":       "analyst_escalation",
            "analyst_id":       ANALYST_ID,
            "analyst_action":   "escalated",
            "confidence_score": cls.get("confidence_score"),
            "reasoning_text":   cls.get("reasoning_text"),
            "analyst_note":     f"{shipment_id} escalated to {assignee}. Notes: {notes}"
        }).execute()

        return {"status": "ok", "message": f"Escalated to {assignee}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Override HS Code ──────────────────────────────────────────────
@router.post("/api/shipments/{shipment_id}/override-hs")
async def override_hs_code(shipment_id: str, request: Request):
    try:
        body    = await request.json()
        hs_code = (body.get("hs_code") or "").strip()
        reason  = (body.get("reason")  or "").strip()
        if not hs_code or not reason:
            raise HTTPException(status_code=400, detail="hs_code and reason are required")

        supabase = request.app.state.supabase
        ship = supabase.table("shipments").select("id") \
            .eq("sap_shipment_id", shipment_id).single().execute()
        if not ship.data:
            raise HTTPException(status_code=404, detail="Shipment not found")

        cls_res = supabase.table("hs_classifications") \
            .select("id, ai_hs_code, confidence_score, reasoning_text") \
            .eq("shipment_id", ship.data["id"]) \
            .order("created_at", desc=True).limit(1).execute()

        original_hs         = cls_res.data[0].get("ai_hs_code", "UNKNOWN")    if cls_res.data else "UNKNOWN"
        original_confidence = cls_res.data[0].get("confidence_score", 0)      if cls_res.data else 0
        original_reasoning  = cls_res.data[0].get("reasoning_text", "")       if cls_res.data else ""

        if cls_res.data:
            supabase.table("hs_classifications").update({
                "analyst_override_hs": hs_code,
                "final_hs_code":       hs_code,
            }).eq("id", cls_res.data[0]["id"]).execute()
        else:
            supabase.table("hs_classifications").insert({
                "shipment_id":         ship.data["id"],
                "analyst_override_hs": hs_code,
                "final_hs_code":       hs_code,
                "module_a_status":     "auto_passed",
            }).execute()

        supabase.table("shipments").update({"status": "approved"}) \
            .eq("sap_shipment_id", shipment_id).execute()

        # Analyst override log
        supabase.table("audit_trail").insert({
            "shipment_id":      ship.data["id"],
            "event_type":       "analyst_override",
            "analyst_id":       ANALYST_ID,
            "analyst_action":   "override",
            "confidence_score": original_confidence,
            "reasoning_text":   original_reasoning,
            "analyst_note":     f"{shipment_id} HS code overridden to {hs_code} by {ANALYST_NAME}. Reason: {reason}"
        }).execute()

        # Step 5 — Feedback loop: training signal
        try:
            supabase.table("audit_trail").insert({
                "shipment_id":      ship.data["id"],
                "event_type":       "model_feedback",
                "analyst_id":       ANALYST_ID,
                "analyst_action":   "training_signal",
                "confidence_score": original_confidence,
                "reasoning_text":   original_reasoning,
                "analyst_note": (
                    f"[TRAINING SIGNAL] AI predicted: {original_hs} ({original_confidence}% confidence). "
                    f"Analyst corrected to: {hs_code}. Reason: {reason}"
                )
            }).execute()
            print(f"[FEEDBACK LOOP] {shipment_id}: AI={original_hs} → Analyst={hs_code} | Reason: {reason}")
        except Exception:
            pass

        return {"status": "ok", "message": f"HS overridden to {hs_code}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Layer 4: Submit Batch to SAP ──────────────────────────────────
@router.post("/api/admin/process-all")
async def process_all_pending(request: Request):
    """Run classify → match-fta → landed-cost on every pending shipment."""
    from classifier.hs_classifier import classify_hs_code
    from calculator.fta_matcher import match_fta
    from calculator.landed_cost import calculate_landed_cost

    supabase = request.app.state.supabase
    ships = supabase.table("shipments").select("sap_shipment_id") \
        .eq("status", "pending").execute()

    results = {"processed": 0, "failed": 0, "errors": []}
    for row in (ships.data or []):
        sid = row["sap_shipment_id"]
        try:
            classify_hs_code(sid, supabase)
            await match_fta(sid, supabase)
            await calculate_landed_cost(sid, supabase)
            results["processed"] += 1
            print(f"[batch] {sid} done")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"id": sid, "error": str(e)})
            print(f"[batch] {sid} failed: {e}")

    return {"status": "ok", "results": results}


@router.post("/api/shipments/submit-batch")
async def submit_batch_to_sap(request: Request):
    try:
        body = await request.json()
        shipment_ids = body.get("shipment_ids", [])
        if not shipment_ids:
            raise HTTPException(status_code=400, detail="No shipment IDs provided")

        supabase  = request.app.state.supabase
        submitted = []
        failed    = []

        for sap_id in shipment_ids:
            try:
                ship = supabase.table("shipments").select("id, status") \
                    .eq("sap_shipment_id", sap_id).single().execute()
                if not ship.data:
                    failed.append({"id": sap_id, "reason": "not found"})
                    continue
                if ship.data["status"] != "approved":
                    failed.append({"id": sap_id, "reason": f"status is {ship.data['status']}, not approved"})
                    continue

                cls = _get_latest_cls(supabase, ship.data["id"])
                lc  = supabase.table("landed_costs").select("total_duty_myr, total_landed_cost_usd") \
                    .eq("shipment_id", ship.data["id"]) \
                    .order("created_at", desc=True).limit(1).execute()

                hs_code     = cls.get("final_hs_code", "UNKNOWN")
                duty_amount = lc.data[0].get("total_duty_myr", 0.0) if lc.data else 0.0

                supabase.table("shipments").update({"status": "submitted"}) \
                    .eq("sap_shipment_id", sap_id).execute()

                sap_result = await write_duty_to_sap(sap_id, hs_code, duty_amount)

                supabase.table("audit_trail").insert({
                    "shipment_id":      ship.data["id"],
                    "event_type":       "sap_writeback",
                    "analyst_id":       ANALYST_ID,
                    "analyst_action":   "submitted_to_sap",
                    "confidence_score": cls.get("confidence_score"),
                    "reasoning_text":   cls.get("reasoning_text"),
                    "analyst_note": (
                        f"{sap_id} duty figures written to SAP S/4HANA (mock) by {ANALYST_NAME}. "
                        f"HS: {hs_code} | Duty: MYR {duty_amount} | "
                        f"Doc: {sap_result.get('sap_document_number', 'N/A')}"
                    )
                }).execute()

                submitted.append(sap_id)

            except Exception as e:
                failed.append({"id": sap_id, "reason": str(e)})

        return {
            "status": "ok",
            "submitted": len(submitted),
            "submitted_ids": submitted,
            "failed": failed
        }

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


# ── Layer 4: Compliance PDF ───────────────────────────────────────
@router.get("/api/shipments/{shipment_id}/compliance-pdf")
async def download_compliance_pdf(shipment_id: str, request: Request):
    try:
        supabase = request.app.state.supabase

        ship = supabase.table("shipments") \
            .select("*, hs_classifications(*), fta_results(*), landed_costs(*)") \
            .eq("sap_shipment_id", shipment_id).single().execute()
        if not ship.data:
            raise HTTPException(status_code=404, detail="Shipment not found")

        audit = supabase.table("audit_trail").select("*") \
            .eq("shipment_id", ship.data["id"]) \
            .order("created_at").execute()

        pdf_bytes = generate_compliance_pdf(ship.data, audit.data or [])

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=compliance_{shipment_id}.pdf"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Data Ingestion Admin Routes ───────────────────────────────────
# These let you trigger the real data pipeline manually from the UI
# The same jobs also run on schedule via scheduler.py

@router.get("/api/admin/ingestion-status")
async def get_ingestion_status(request: Request):
    """Show when each job last ran and what the DB contains."""
    try:
        supabase = request.app.state.supabase

        fta_rates_count   = len(supabase.table("fta_rates").select("id").execute().data)
        fta_coverage_count = len(supabase.table("fta_coverage").select("id").execute().data)

        # Last gazette alert (most recent PDF processed)
        gazette_last = supabase.table("gazette_alerts") \
            .select("gazette_title,processed_at,is_tariff_related") \
            .order("processed_at", desc=True).limit(5).execute()

        # Check scheduler jobs if available
        scheduler = getattr(request.app.state, "scheduler", None)
        jobs = []
        if scheduler:
            for job in scheduler.get_jobs():
                next_run = job.next_run_time
                jobs.append({
                    "id":       job.id,
                    "name":     job.name,
                    "next_run": str(next_run) if next_run else "paused"
                })

        return {
            "status": "ok",
            "db_counts": {
                "fta_rates":    fta_rates_count,
                "fta_coverage": fta_coverage_count,
            },
            "recent_gazette_pdfs": gazette_last.data,
            "scheduled_jobs": jobs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/admin/run-ingestion/{job}")
async def run_ingestion_job(job: str, request: Request):
    """
    Manually trigger one of the ingestion jobs:
      - gazette   → download & parse latest PDFs from Malaysian Gazette RSS
      - jkdm      → scrape real FTA rates from ezhs.customs.gov.my (needs Playwright)
      - miti      → scrape MITI FTA page list
      - wto       → sync MFN tariff rates from WTO API
      - all       → run gazette + wto (safe, no Playwright required)
    """
    allowed = {"gazette", "jkdm", "miti", "wto", "all"}
    if job not in allowed:
        raise HTTPException(status_code=400, detail=f"Unknown job '{job}'. Choose: {allowed}")

    results = {}
    try:
        if job in ("gazette", "all"):
            from ingestion.gazette_monitor import monitor_gazette_rss
            results["gazette"] = await monitor_gazette_rss()

        if job in ("wto", "all"):
            from ingestion.tariff_sync import sync_tariff_rates
            results["wto"] = await sync_tariff_rates()

        if job in ("jkdm",):
            from ingestion.fta_scraper import scrape_jkdm_rates
            results["jkdm"] = await scrape_jkdm_rates()

        if job in ("miti",):
            from ingestion.fta_scraper import scrape_miti_fta_rates
            results["miti"] = await scrape_miti_fta_rates()

        return {"status": "ok", "job": job, "results": results}
    except Exception as e:
        import traceback
        print(f"[ingestion/{job}] ERROR: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/admin/dry-run-pdf")
async def dry_run_pdf(body: DryRunPdfRequest):
    """
    Debug endpoint: fetch a MITI PDF and print the first 10 rows of each table
    (pages 1-3 only). Does NOT write to the database. Check server terminal for output.
    """
    try:
        import httpx
        from ingestion.pdf_extractor import extract_fta_rates_from_pdf

        content = b""
        async with httpx.AsyncClient(timeout=60, verify=False) as client:
            resp = await client.get(body.pdf_url)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"PDF fetch failed: HTTP {resp.status_code}"
                )
            content = resp.content

        extract_fta_rates_from_pdf(content, body.fta_name, body.origin_country, body.pdf_url, dry_run=True)

        return {
            "status": "ok",
            "message": "Dry run complete — check server terminal for column headers and sample rows",
            "pdf_url": body.pdf_url,
            "fta_name": body.fta_name,
            "origin_country": body.origin_country,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
