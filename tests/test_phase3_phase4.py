import sys
import os
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from sqlmodel import Session, select
from backend.db.session import init_db, engine
from backend.db.models import RecoveryCase, Transaction, AuditLog
from backend.engine.revenue_monitor import RevenueMonitor
from backend.engine.classifier import RootCauseClassifier

def test_revenue_monitor_and_classifier():
    # 1. Initialize SQLite Database
    init_db()
    
    # 2. Read events_dev.csv
    df = pd.read_csv("data/events_dev.csv").fillna("N/A")
    print(f"\n[INFO] Testing Phase 3 (Revenue Monitor) & Phase 4 (Classifier)")
    print(f"[INFO] Ingesting {len(df)} dev dataset events...")
    
    monitor = RevenueMonitor()
    classifier = RootCauseClassifier()
    
    flagged_count = 0
    classified_samples = []
    
    with Session(engine) as session:
        for idx, row in df.iterrows():
            event_dict = row.to_dict()
            
            # Phase 3: Monitor Ingestion & Risk Detection
            is_risk, case = monitor.process_event(event_dict, session=session)
            
            if is_risk and case:
                flagged_count += 1
                
                # Phase 4: Classification
                cls_result = classifier.classify_and_update_case(case, event_dict, session=session)
                
                if len(classified_samples) < 10:
                    classified_samples.append({
                        "case_id": case.id,
                        "transaction_id": event_dict["transaction_id"],
                        "failure_type": event_dict["failure_type"],
                        "amount": event_dict["amount"],
                        "root_cause": cls_result.root_cause,
                        "confidence": cls_result.confidence,
                        "reasoning": cls_result.reasoning
                    })

    print(f"\n[RESULTS] Ingestion & Risk Monitoring Complete:")
    print(f" - Total Events Evaluated: {len(df)}")
    print(f" - Total Flagged At-Risk Revenue Cases: {flagged_count}")
    assert flagged_count == len(df), f"Expected all {len(df)} failed events to be flagged, got {flagged_count}"
    
    print("\n" + "="*80)
    print("SAMPLE FLAGGED CASES & CLASSIFICATION OUTPUT (FIRST 10 CASES)")
    print("="*80)
    
    for i, s in enumerate(classified_samples, 1):
        print(f"\nCase #{i:02d} [{s['case_id']}]")
        print(f"  Transaction ID : {s['transaction_id']}")
        print(f"  Failure Type   : {s['failure_type']}")
        print(f"  Amount (INR)   : {s['amount']:,.2f}")
        print(f"  Root Cause     : {s['root_cause']}")
        print(f"  Confidence     : {s['confidence']*100:.1f}%")
        print(f"  Reasoning      : {s['reasoning']}")

    # Verify Audit Logs in SQLite DB
    with Session(engine) as session:
        audits = session.exec(select(AuditLog)).all()
        print("\n" + "="*80)
        print(f"[VERIFICATION] Audit Log Records in SQLite DB: {len(audits)} audit entries created.")
        print("="*80)

if __name__ == "__main__":
    test_revenue_monitor_and_classifier()
