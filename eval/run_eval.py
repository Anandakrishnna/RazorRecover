import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from datetime import datetime, timezone
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
from backend.engine.agent_loop import run_agent_pipeline

HOLDOUT_CSV = "data/events_holdout.csv"
REPORT_JSON = "eval/report.json"

def run_evaluation():
    if not os.path.exists(HOLDOUT_CSV):
        raise FileNotFoundError(f"Holdout evaluation dataset '{HOLDOUT_CSV}' not found!")

    print(f"[INFO] Loading holdout evaluation dataset from: {HOLDOUT_CSV}")
    df = pd.read_csv(HOLDOUT_CSV).fillna("N/A")
    total_events = len(df)
    print(f"[INFO] Running evaluation pipeline across {total_events} held-out events...\n")

    # Create an isolated in-memory SQLite database session for evaluation run
    eval_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eval_engine)

    revenue_at_risk = 0.0
    potentially_recoverable = 0.0
    successfully_recovered = 0.0

    total_interventions = 0
    unnecessary_interventions = 0
    policy_violations = 0

    cases_breakdown = {
        "RECOVERED": 0,
        "FAILED": 0,
        "ESCALATED": 0,
        "STOPPED": 0
    }

    with Session(eval_engine) as session:
        for idx in range(total_events):
            event_row = df.iloc[idx].to_dict()
            amount = float(event_row.get("amount", 0.0))
            is_recoverable = str(event_row.get("is_recoverable", "")).strip().lower() == "true"

            revenue_at_risk += amount
            if is_recoverable:
                potentially_recoverable += amount

            # Execute full agent pipeline (with deterministic seed per event index)
            trace = run_agent_pipeline(event_dict=event_row, session=session, seed=idx)

            if not trace.get("at_risk"):
                continue

            decision = trace.get("agent_decision", {})
            action_taken = decision.get("allowed_action_taken", "")
            policy_check_result = decision.get("policy_check_result", "")
            final_status = trace.get("final_case_status", "OPEN")

            # Track case status
            if final_status in cases_breakdown:
                cases_breakdown[final_status] += 1
            else:
                cases_breakdown["FAILED"] += 1

            if final_status == "RECOVERED":
                successfully_recovered += amount

            # Track policy violations (Must be 0)
            if policy_check_result == "POLICY_VIOLATED":
                policy_violations += 1

            # Track unnecessary interventions
            non_intervention_actions = {
                "log_and_suppress", "STOP", "human_escalation", "pause_subscription_and_escalate"
            }
            if action_taken not in non_intervention_actions:
                total_interventions += 1
                if not is_recoverable:
                    unnecessary_interventions += 1

    recovery_rate_pct = round((successfully_recovered / revenue_at_risk * 100), 2) if revenue_at_risk > 0 else 0.0
    unnecessary_interventions_pct = round((unnecessary_interventions / total_interventions * 100), 2) if total_interventions > 0 else 0.0

    report = {
        "evaluation_metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dataset_file": HOLDOUT_CSV,
            "total_heldout_events": total_events,
            "status": "UN_TUNED_FINAL_EVALUATION"
        },
        "financial_metrics": {
            "revenue_at_risk_inr": round(revenue_at_risk, 2),
            "potentially_recoverable_inr": round(potentially_recoverable, 2),
            "successfully_recovered_inr": round(successfully_recovered, 2),
            "recovery_rate_pct": recovery_rate_pct
        },
        "agent_performance_metrics": {
            "total_interventions_executed": total_interventions,
            "unnecessary_interventions_count": unnecessary_interventions,
            "unnecessary_interventions_pct": unnecessary_interventions_pct,
            "policy_violations_count": policy_violations,
            "target_policy_violations": 0
        },
        "case_outcomes_breakdown": {
            "recovered_cases": cases_breakdown["RECOVERED"],
            "failed_cases": cases_breakdown["FAILED"],
            "escalated_cases": cases_breakdown["ESCALATED"],
            "stopped_cases": cases_breakdown["STOPPED"]
        }
    }

    os.makedirs(os.path.dirname(REPORT_JSON), exist_ok=True)
    with open(REPORT_JSON, "w") as f:
        json.dump(report, f, indent=2)

    print("================================================================================")
    print("                RAZORRECOVER — EVALUATION SUITE RESULTS                        ")
    print("================================================================================\n")
    print(f" Total Held-out Events          : {total_events}")
    print(f" Total Revenue at Risk (INR)    : INR {revenue_at_risk:,.2f}")
    print(f" Potentially Recoverable (INR)  : INR {potentially_recoverable:,.2f}")
    print(f" Successfully Recovered (INR)   : INR {successfully_recovered:,.2f}")
    print(f" Recovery Rate (%)              : {recovery_rate_pct}%")
    print(f" Unnecessary Interventions (%)  : {unnecessary_interventions_pct}% ({unnecessary_interventions}/{total_interventions})")
    print(f" Policy Violations (Target 0)   : {policy_violations}")
    print(f" Case Outcomes Breakdown        : {cases_breakdown}\n")
    print(f"[SUCCESS] Evaluation report exported to: {REPORT_JSON}")
    print("================================================================================")

    return report

if __name__ == "__main__":
    run_evaluation()
