"""HTTP entrypoint to run the full agent pipeline for a business."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder

from agents.orchestrator import laksa_agent

router = APIRouter(tags=["agent"])


@router.post("/run-agent/{business_id}")
def jalankan_agen(
    business_id: int,
    trigger: str = Query("manual", description="manual | webhook | csv_upload | scheduled"),
    tanggal: Optional[date] = Query(None, description="Opsional: tanggal laporan (demo)"),
):
    """Satu HTTP call untuk menjalankan seluruh pipeline agen."""
    state_awal = {
        "business_id": business_id,
        "trigger": trigger,
        "tanggal_laporan": tanggal or date.today(),
        "errors": [],
    }
    return jsonable_encoder(laksa_agent.invoke(state_awal))
