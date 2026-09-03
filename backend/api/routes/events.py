from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from backend.db.session import get_session
from backend.engine.agent_loop import run_agent_pipeline

router = APIRouter(prefix="/events", tags=["Events"])

@router.post("/ingest", status_code=status.HTTP_200_OK)
def ingest_event(
    event: Dict[str, Any],
    session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """
    Ingests a revenue-loss event & triggers autonomous agent pipeline loop.
    Returns case status, recovery predictions, agent decision, execution dispatch, and audit trail.
    """
    if not event or "transaction_id" not in event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must include 'transaction_id'."
        )

    try:
        trace = run_agent_pipeline(event_dict=event, session=session)
        return trace
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent pipeline processing failed: {str(e)}"
        )
