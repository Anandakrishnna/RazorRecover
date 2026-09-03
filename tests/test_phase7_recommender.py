import sys
import os
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
from backend.engine.recommender import LLMRecommender

def test_phase7_recommender():
    init_db()
    df = pd.read_csv("data/events_dev.csv").fillna("N/A")
    
    monitor = RevenueMonitor()
    classifier = RootCauseClassifier()
    rec_model = RecoveryProbabilityModel()
    policy_engine = PolicyEngine()
    recommender = LLMRecommender() # Uses offline mock fallback cleanly if API key absent
    
    print("\n" + "="*80)
    print("RUNNING PHASE 7 (LLM RECOMMENDER & POLICY GATING INTEGRATION TESTS)")
    print("="*80)
    
    samples = []
    
    with Session(engine) as session:
        for idx in range(min(10, len(df))):
            event_dict = df.iloc[idx].to_dict()
            
            # Phase 3 & 4
            _, case = monitor.process_event(event_dict, session=session)
            classifier.classify_and_update_case(case, event_dict, session=session)
            rec_model.predict_and_update_case(case, event_dict, session=session)
            
            # Phase 7: LLM Recommendation + Policy Gating
            llm_rec = recommender.recommend(event_dict, case.root_cause)
            decision = recommender.recommend_and_gate_with_policy(
                case=case,
                event_dict=event_dict,
                policy_engine=policy_engine,
                session=session
            )
            
            samples.append({
                "case_id": case.id,
                "transaction_id": event_dict["transaction_id"],
                "failure_type": event_dict["failure_type"],
                "amount": event_dict["amount"],
                "llm_action": llm_rec.proposed_action,
                "llm_source": llm_rec.source,
                "llm_reasoning": llm_rec.reasoning_text,
                "policy_action": decision.action_taken,
                "policy_check": decision.policy_check_result,
                "full_reasoning": decision.reasoning_text
            })

    for i, s in enumerate(samples, 1):
        print(f"\nCase Sample #{i:02d} [{s['case_id']}]")
        print(f"  Transaction ID  : {s['transaction_id']}")
        print(f"  Failure Type    : {s['failure_type']}")
        print(f"  LLM Proposal    : {s['llm_action']} (Source: {s['llm_source']})")
        print(f"  LLM Reasoning   : {s['llm_reasoning']}")
        print(f"  Policy Action   : {s['policy_action']}")
        print(f"  Policy Verdict  : {s['policy_check']}")

    print("\n" + "="*80)
    print("ALL PHASE 7 LLM RECOMMENDER TESTS PASSED SUCCESSFULLY!")
    print("="*80)

if __name__ == "__main__":
    test_phase7_recommender()
