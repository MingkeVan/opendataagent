from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.api import RunCancelResponse
from app.services.run_service import get_run
from app.services.stream_service import iter_run_stream

router = APIRouter()


@router.get("/{run_id}/stream")
async def stream_run_route(
    run_id: str,
    after_seq: int = 0,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    session: Session = Depends(get_db),
):
    run = get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    resume_seq = after_seq
    if last_event_id and last_event_id.isdigit():
        resume_seq = max(resume_seq, int(last_event_id))
    return StreamingResponse(
        iter_run_stream(run_id, resume_seq),
        media_type="text/event-stream",
        headers={
            "x-vercel-ai-ui-message-stream": "v1",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{run_id}/cancel", response_model=RunCancelResponse)
def cancel_run_route(run_id: str, session: Session = Depends(get_db)) -> dict:
    run = get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run.cancel_requested = True
    session.commit()
    return {"runId": run.id, "status": "cancel_requested"}
