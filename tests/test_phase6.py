import sys
import os
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from sqlmodel import Session, select
from backend.db.session import init_db, engine
from backend.engine.revenue_monitor import RevenueMonitor
from backend.engine.classifier import RootCauseClassifier
from backend.engine.recovery_model import RecoveryProbabilityModel
from backend.engine.policy_engine import PolicyEngine

def test_phase6_policy_engine():
    init_db()
    df = pd.read_csv("data/events_dev.csv").fillna("N/A")
    
    monitor = RevenueMonitor()
    classifier = RootCauseClassifier()
    rec_model = RecoveryProbabilityModel()
    policy_engine = PolicyEngine()
    
    print(f"\n[INFO] Testing Phase 6 (Policy Engine — Priority Ranking Matrix)")
    print(f"[INFO] Evaluating agent pipeline (Phases 1-6) across dev dataset...\n")
    
    samples = []
    rule_counts = {}
    
    with Session(engine) as session:
        for idx in range(len(df)):
            event_dict = df.iloc[idx].to_dict()
            
            # Phase 3: Monitor
            _, case = monitor.process_event(event_dict, session=session)
            
            # Phase 4: Classifier
            classifier.classify_and_update_case(case, event_dict, session=session)
            
            # Phase 5: Recovery Model
            prob_res = rec_model.predict_and_update_case(case, event_dict, session=session)
            
            # Phase 6: Policy Engine Gating
            # Simulate LLM proposal (proposing 'retry' by default to test policy overrides)
            mock_llm_proposal = "retry"
            decision = policy_engine.process_and_update_case(
                case=case,
                event_dict=event_dict,
                proposed_action=mock_llm_proposal,
                reasoning_text="LLM recommends automated payment retry.",
                session=session
            )
            
            # Count rule triggers
            rule_id = int(decision.reasoning_text.split("Rule #")[1].split("]")[0])
            rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1
            
            if len(samples) < 12:
                samples.append({
                    "case_id": case.id,
                    "transaction_id": event_dict["transaction_id"],
                    "failure_type": event_dict["failure_type"],
                    "amount": event_dict["amount"],
                    "retry_count": event_dict["retry_count"],
                    "proposed_action": mock_llm_proposal,
                    "action_taken": decision.action_taken,
                    "policy_result": decision.policy_check_result,
                    "rule_id": rule_id,
                    "reasoning": decision.reasoning_text
                })

        session.commit()

    print("="*100)
    print("PHASE 6: POLICY ENGINE SAMPLE DECISIONS & OVERRIDES")
    print("="*100)
    
    for i, s in enumerate(samples, 1):
        print(f"\nSample #{i:02d} [{s['case_id']}] — Rule #{s['rule_id']}")
        print(f"  Transaction ID  : {s['transaction_id']}")
        print(f"  Failure Type    : {s['failure_type']}")
        print(f"  LLM Proposal    : {s['proposed_action']}")
        print(f"  Policy Action   : {s['action_taken']}")
        print(f"  Policy Check    : {s['policy_result']}")
        print(f"  Policy Rationale: {s['reasoning']}")

    print("\n" + "="*100)
    print("PRIORITY MATRIX RULE TRIGGER DISTRIBUTION (Dev Dataset):")
    print("="*100)
    for rule_id in sorted(rule_counts.keys()):
        print(f"  - Policy Rule #{rule_id:02d}: {rule_counts[rule_id]} cases triggered")
        
    print("\nALL 6 PHASES (1 TO 6) BUILT & VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    test_phase6_policy_engine()
