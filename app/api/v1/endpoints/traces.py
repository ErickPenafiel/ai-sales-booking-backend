from fastapi import APIRouter, Query
from typing import List, Dict

from app.services import tracing

router = APIRouter()


@router.get("/traces", tags=["Traces"])
def get_traces(limit: int = Query(100, ge=1, le=1000)) -> List[Dict]:
    """Return last `limit` traces recorded locally."""
    return tracing.list_traces(limit)
