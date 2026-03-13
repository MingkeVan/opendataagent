from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.api import RunCancelResponse
from app.services.run_service import get_run
from app.services.stream_service import iter_run_stream

router = APIRouter()


@router.get("/{run_id}/stream")
async def stream_run_route(run_id: str, after_seq: int = 0, session: Session = Depends(get_db)):
    run = get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return StreamingResponse(iter_run_stream(run_id, after_seq), media_type="text/event-stream")


@router.post("/{run_id}/cancel", response_model=RunCancelResponse)
def cancel_run_route(run_id: str, session: Session = Depends(get_db)) -> dict:
    run = get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run.cancel_requested = True
    session.commit()
    return {"runId": run.id, "status": "cancel_requested"}

