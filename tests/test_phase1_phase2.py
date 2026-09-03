import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uuid
import pandas as pd
from sqlmodel import Session, select
from backend.db.session import init_db, engine
from backend.db.models import Merchant, Customer, Transaction, RecoveryCase

def test_phase1_and_phase2():
    # 1. Verify Phase 1 datasets exist
    assert os.path.exists("data/events_dev.csv"), "events_dev.csv missing!"
    assert os.path.exists("data/events_holdout.csv"), "events_holdout.csv missing!"
    
    dev_df = pd.read_csv("data/events_dev.csv")
    holdout_df = pd.read_csv("data/events_holdout.csv")
    
    print(f"[TEST] Phase 1 Datasets Loaded:")
    print(f"       - dev set: {len(dev_df)} events")
    print(f"       - holdout set: {len(holdout_df)} events")
    assert len(dev_df) == 800
    assert len(holdout_df) == 200
    
    # 2. Verify Phase 2 SQLite Database Initialization
    init_db()
    
    uid = uuid.uuid4().hex[:6]
    merch_id = f"merch_{uid}"
    cust_id = f"cust_{uid}"
    txn_id = f"txn_{uid}"
    case_id = f"case_{uid}"
    
    with Session(engine) as session:
        merchant = Merchant(id=merch_id, name="Test Merchant Store")
        customer = Customer(
            id=cust_id,
            merchant_id=merch_id,
            name="Alice Test",
            subscription_status="ACTIVE",
            previous_recovery_outcome="RECOVERED",
            history_json='{"total_orders": 3, "total_spent": 9500.0}'
        )
        transaction = Transaction(
            id=txn_id,
            merchant_id=merch_id,
            customer_id=cust_id,
            amount=4500.0,
            method="card",
            status="FAILED",
            failure_type="card_expired",
            retry_count=0
        )
        case = RecoveryCase(
            id=case_id,
            transaction_id=txn_id,
            revenue_at_risk=4500.0,
            root_cause="CARD_EXPIRED",
            confidence=0.95,
            recovery_probability=0.85,
            expected_recovery_value=3825.0,
            status="OPEN"
        )
        
        session.add(merchant)
        session.add(customer)
        session.add(transaction)
        session.add(case)
        session.commit()
        
        fetched_case = session.get(RecoveryCase, case_id)
        print(f"[TEST] Phase 2 DB Insert & Retrieval Verified:")
        print(f"       - Case ID: {fetched_case.id}")
        print(f"       - Revenue at Risk: INR {fetched_case.revenue_at_risk}")
        print(f"       - Root Cause: {fetched_case.root_cause}")
        print(f"       - Expected Recovery Value: INR {fetched_case.expected_recovery_value}")
        
        assert fetched_case.revenue_at_risk == 4500.0
        assert fetched_case.expected_recovery_value == 3825.0

    print("\nALL PHASE 1 & PHASE 2 TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_phase1_and_phase2()
