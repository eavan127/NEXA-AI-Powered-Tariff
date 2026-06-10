from pydantic import BaseModel
from typing import Optional

class ProcessBatchRequest(BaseModel):
    shipment_ids: Optional[list[str]] = None
    run_all_pending: Optional[bool] = False

class ApproveRequest(BaseModel):
    analyst_id: str
    note: Optional[str] = None

class RejectRequest(BaseModel):
    analyst_id: str
    note: str
    reason: str

class OverrideHSRequest(BaseModel):
    analyst_id: str
    correct_hs_code: str
    reason: str

class DryRunPdfRequest(BaseModel):
    pdf_url: str
    fta_name: str = "ATIGA"
    origin_country: str = "Unknown"

class MockRateChangeRequest(BaseModel):
    hs_code: str = "7604.29"
    old_rate: float = 25.0
    new_rate: float = 35.0
    effective_date: str = "2026-06-01"

class RecalculateRequest(BaseModel):
    analyst_id: str = "SARAH_LIM"
    alert_id: Optional[str] = None

class ReapproveRequest(BaseModel):
    analyst_id: str = "JAMES_TAN"
    action: str  # "approve_new_rate" | "escalate_manager"
    note: Optional[str] = ""

class Case3ActionRequest(BaseModel):
    analyst_id: str = "JAMES_TAN"
    note: Optional[str] = ""
