import sys
import os
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from sqlmodel import Session, select
from backend.db.session import init_db, engine
from backend.db.models import RecoveryCase
from backend.engine.revenue_monitor import RevenueMonitor
from backend.engine.classifier import RootCauseClassifier
from backend.engine.recovery_model import RecoveryProbabilityModel

def test_phase5_recovery_model():
    init_db()
    df = pd.read_csv("data/events_dev.csv").fillna("N/A")
    
    monitor = RevenueMonitor()
    classifier = RootCauseClassifier()
    rec_model = RecoveryProbabilityModel()
    
    print(f"\n[INFO] Testing Phase 5 (Recovery Probability Model)")
    print(f"[INFO] Ingesting & scoring sample events from events_dev.csv...\n")
    
    samples = []
    
    with Session(engine) as session:
        for idx in range(min(15, len(df))):
            event_dict = df.iloc[idx].to_dict()
            
            # Phase 3 & 4
            _, case = monitor.process_event(event_dict, session=session)
            classifier.classify_and_update_case(case, event_dict, session=session)
            
            # Phase 5
            prob_res = rec_model.predict_and_update_case(case, event_dict, session=session)
            
            samples.append({
                "case_id": case.id,
                "transaction_id": event_dict["transaction_id"],
                "failure_type": event_dict["failure_type"],
                "amount": event_dict["amount"],
                "retry_count": event_dict["retry_count"],
                "probability": prob_res.recovery_probability,
                "expected_value": prob_res.expected_recovery_value,
                "risk_tier": prob_res.risk_tier,
                "explanation": prob_res.explanation
            })

    print("="*100)
    print("PHASE 5: RECOVERY PROBABILITY MODEL SAMPLE OUTPUTS")
    print("="*100)
    
    for i, s in enumerate(samples, 1):
        print(f"\nSample #{i:02d} [{s['case_id']}] — {s['failure_type'].upper()}")
        print(f"  Transaction ID : {s['transaction_id']}")
        print(f"  Amount (INR)   : INR {s['amount']:,.2f}")
        print(f"  Retry Count    : {s['retry_count']}")
        print(f"  Probability P  : {s['probability']*100:.1f}%")
        print(f"  Expected Value : INR {s['expected_value']:,.2f}")
        print(f"  Risk Tier      : {s['risk_tier']}")
        print(f"  Model Drivers  : {s['explanation']}")

if __name__ == "__main__":
    test_phase5_recovery_model()
