import os
import pandas as pd
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, create_engine
from backend.db.session import get_session
from backend.engine.agent_loop import run_agent_pipeline

router = APIRouter(prefix="/metrics", tags=["Metrics & Evaluation"])

HOLDOUT_CSV = "data/events_holdout.csv"

@router.get("/eval", status_code=status.HTTP_200_OK)
def run_evaluation_suite() -> Dict[str, Any]:
    """
    Executes the evaluation suite against the 200 held-out evaluation dataset events (data/events_holdout.csv).
    Calculates PRD Section 10 verification metrics (revenue at risk, recovered revenue, recovery rate %, policy violations, escalations).
    Uses an isolated in-memory database session so evaluation runs do not mutate production case data.
    """
    if not os.path.exists(HOLDOUT_CSV):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holdout dataset file '{HOLDOUT_CSV}' not found."
        )

    try:
        df = pd.read_csv(HOLDOUT_CSV).fillna("N/A")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load evaluation dataset: {str(e)}"
        )

    # Use an isolated in-memory DB engine for evaluation run
    eval_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    from sqlmodel import SQLModel
    SQLModel.metadata.create_all(eval_engine)

    total_events = len(df)
    total_revenue_at_risk = 0.0
    potentially_recoverable_revenue = 0.0
    successfully_recovered_revenue = 0.0
    
    total_interventions = 0
    unnecessary_interventions = 0
    policy_violations = 0
    escalated_cases = 0
    stopped_cases = 0
    failed_cases = 0
    recovered_cases = 0

    with Session(eval_engine) as eval_session:
        for idx in range(total_events):
            event_row = df.iloc[idx].to_dict()
            amount = float(event_row.get("amount", 0.0))
            is_recoverable = str(event_row.get("is_recoverable", "")).lower() == "true"
            
            total_revenue_at_risk += amount
            if is_recoverable:
                potentially_recoverable_revenue += amount

            # Run agent pipeline for event
            # Use seed=idx for deterministic probabilistic verification rolls
            trace = run_agent_pipeline(event_dict=event_row, session=eval_session, seed=idx)

            if not trace.get("at_risk"):
                continue

            decision = trace.get("agent_decision", {})
            action_taken = decision.get("allowed_action_taken", "")
            policy_result = decision.get("policy_check_result", "")
            verif = trace.get("verification_result", {})
            final_status = trace.get("final_case_status", "")

            # Policy violation tracking (must be 0 per Section 10)
            # Policy Engine strictly gates all executed actions, overriding invalid recommendations.
            if policy_result == "POLICY_VIOLATED":
                policy_violations += 1

            # Interventions tracking
            if action_taken not in ["log_and_suppress", "STOP", "human_escalation", "pause_subscription_and_escalate"]:
                total_interventions += 1
                if not is_recoverable:
                    unnecessary_interventions += 1

            # Status tracking
            if final_status == "RECOVERED":
                recovered_cases += 1
                successfully_recovered_revenue += amount
            elif final_status == "ESCALATED":
                escalated_cases += 1
            elif final_status == "STOPPED":
                stopped_cases += 1
            else:
                failed_cases += 1

    recovery_rate_pct = round((successfully_recovered_revenue / total_revenue_at_risk * 100), 2) if total_revenue_at_risk > 0 else 0.0
    unnecessary_interventions_pct = round((unnecessary_interventions / total_interventions * 100), 2) if total_interventions > 0 else 0.0

    return {
        "heldout_events": total_events,
        "revenue_at_risk": round(total_revenue_at_risk, 2),
        "potentially_recoverable_revenue": round(potentially_recoverable_revenue, 2),
        "successfully_recovered_revenue": round(successfully_recovered_revenue, 2),
        "recovery_rate_pct": recovery_rate_pct,
        "unnecessary_interventions_pct": unnecessary_interventions_pct,
        "policy_violations": policy_violations,
        "cases_breakdown": {
            "recovered": recovered_cases,
            "failed": failed_cases,
            "escalated": escalated_cases,
            "stopped": stopped_cases
        }
    }
