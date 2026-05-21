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
