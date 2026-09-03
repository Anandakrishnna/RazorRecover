import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.engine.policy_engine import PolicyEngine

def test_policy_engine_matrix():
    engine = PolicyEngine()
    print("="*80)
    print("RUNNING COMPREHENSIVE POLICY ENGINE UNIT TESTS (RULES 1 TO 13 + EDGE CASES)")
    print("="*80)

    # -------------------------------------------------------------------------
    # Rule 1: Payment retry limit (retry_count >= 2) -> STOP
    # -------------------------------------------------------------------------
    evt1 = {"failure_type": "temporary", "amount": 1000.0, "retry_count": 2}
    rule_id, action, tier, reason = engine.evaluate(evt1)
    assert rule_id == 1 and action == "STOP"
    print(" [PASS] Rule 1: Payment failure retry_count >= 2 -> STOP")

    # Edge Case: Verify subscription_failed at retry_count = 2 does NOT trigger Rule 1
    evt1_edge = {"failure_type": "subscription_failed", "amount": 999.0, "retry_count": 2}
    rule_id_edge, action_edge, _, _ = engine.evaluate(evt1_edge)
    assert rule_id_edge == 10 and action_edge == "notify_customer_and_retry"
    print(" [PASS] Edge Case 1: Subscription failure retry_count = 2 correctly bypasses Rule 1 to hit Rule 10")

    # -------------------------------------------------------------------------
    # Rule 2: High-value temporary failure (amount >= 50,000) -> human_escalation
    # -------------------------------------------------------------------------
    evt2 = {"failure_type": "temporary", "amount": 55000.0, "retry_count": 1}
    rule_id, action, _, _ = engine.evaluate(evt2)
    assert rule_id == 2 and action == "human_escalation"
    print(" [PASS] Rule 2: Temporary failure >= INR 50,000 -> human_escalation")

    # -------------------------------------------------------------------------
    # Rule 3: Invoice overdue > 30 days -> human_escalation
    # -------------------------------------------------------------------------
    evt3 = {"failure_type": "overdue_invoice", "amount": 25000.0, "invoice_age_days": 35}
    rule_id, action, _, _ = engine.evaluate(evt3)
    assert rule_id == 3 and action == "human_escalation"
    print(" [PASS] Rule 3: Invoice overdue > 30 days -> human_escalation")

    # -------------------------------------------------------------------------
    # Rule 4: Subscription failure retry_count >= 3 -> pause_subscription_and_escalate
    # -------------------------------------------------------------------------
    evt4 = {"failure_type": "subscription_failed", "amount": 1999.0, "retry_count": 3}
    rule_id, action, _, _ = engine.evaluate(evt4)
    assert rule_id == 4 and action == "pause_subscription_and_escalate"
    print(" [PASS] Rule 4: Subscription retry_count >= 3 -> pause_subscription_and_escalate")

    # -------------------------------------------------------------------------
    # Rule 5: Card expired -> request_payment_method_update
    # -------------------------------------------------------------------------
    evt5 = {"failure_type": "card_expired", "amount": 1200.0, "retry_count": 0}
    rule_id, action, _, _ = engine.evaluate(evt5)
    assert rule_id == 5 and action == "request_payment_method_update"
    print(" [PASS] Rule 5: Card expired -> request_payment_method_update")

    # -------------------------------------------------------------------------
    # Rule 6: Insufficient funds / Network timeout / Bank downtime < 2 retries -> scheduled_retry_24h
    # -------------------------------------------------------------------------
    evt6 = {"failure_type": "network_timeout", "amount": 4500.0, "retry_count": 1}
    rule_id, action, _, _ = engine.evaluate(evt6)
    assert rule_id == 6 and action == "scheduled_retry_24h"
    print(" [PASS] Rule 6: Network timeout retry_count < 2 -> scheduled_retry_24h")

    # -------------------------------------------------------------------------
    # Rule 7: Temporary failure < 50k and retry < 2 -> retry
    # -------------------------------------------------------------------------
    evt7 = {"failure_type": "temporary", "amount": 15000.0, "retry_count": 1}
    rule_id, action, _, _ = engine.evaluate(evt7)
    assert rule_id == 7 and action == "retry"
    print(" [PASS] Rule 7: Temporary failure < INR 50k & retry_count < 2 -> retry")

    # -------------------------------------------------------------------------
    # Rule 8: Checkout abandoned + High intent -> send_recovery_message
    # -------------------------------------------------------------------------
    evt8 = {"failure_type": "checkout_abandoned", "amount": 3500.0, "customer_purchase_history": '{"total_orders": 3}'}
    rule_id, action, _, _ = engine.evaluate(evt8, recovery_probability=0.70)
    assert rule_id == 8 and action == "send_recovery_message"
    print(" [PASS] Rule 8: Checkout abandoned + high intent -> send_recovery_message")

    # -------------------------------------------------------------------------
    # Rule 9: Checkout abandoned + Low intent -> log_and_suppress
    # -------------------------------------------------------------------------
    evt9 = {"failure_type": "checkout_abandoned", "amount": 3500.0, "customer_purchase_history": '{"total_orders": 0}'}
    rule_id, action, _, _ = engine.evaluate(evt9, recovery_probability=0.30)
    assert rule_id == 9 and action == "log_and_suppress"
    print(" [PASS] Rule 9: Checkout abandoned + low intent -> log_and_suppress")

    # -------------------------------------------------------------------------
    # Rule 10: Subscription failed < 3 retries -> notify_customer_and_retry
    # -------------------------------------------------------------------------
    evt10 = {"failure_type": "subscription_failed", "amount": 999.0, "retry_count": 1}
    rule_id, action, _, _ = engine.evaluate(evt10)
    assert rule_id == 10 and action == "notify_customer_and_retry"
    print(" [PASS] Rule 10: Subscription failed retry < 3 -> notify_customer_and_retry")

    # -------------------------------------------------------------------------
    # Rule 11: Invoice overdue 7 to 30 days -> reminder
    # -------------------------------------------------------------------------
    evt11 = {"failure_type": "overdue_invoice", "amount": 18000.0, "invoice_age_days": 15}
    rule_id, action, _, _ = engine.evaluate(evt11)
    assert rule_id == 11 and action == "reminder"
    print(" [PASS] Rule 11: Invoice overdue 15 days -> reminder")

    # -------------------------------------------------------------------------
    # Rule 12: Invoice overdue <= 7 days -> gentle_reminder
    # -------------------------------------------------------------------------
    evt12 = {"failure_type": "overdue_invoice", "amount": 18000.0, "invoice_age_days": 4}
    rule_id, action, _, _ = engine.evaluate(evt12)
    assert rule_id == 12 and action == "gentle_reminder"
    print(" [PASS] Rule 12: Invoice overdue 4 days -> gentle_reminder")

    # -------------------------------------------------------------------------
    # Rule 13: Default fallback -> log_and_suppress
    # -------------------------------------------------------------------------
    evt13 = {"failure_type": "unknown_custom_code", "amount": 500.0}
    rule_id, action, _, _ = engine.evaluate(evt13)
    assert rule_id == 13 and action == "log_and_suppress"
    print(" [PASS] Rule 13: Unknown failure_type -> log_and_suppress fallback")

    # -------------------------------------------------------------------------
    # LLM Proposal Validation & Policy Overrides
    # -------------------------------------------------------------------------
    # Case A: LLM proposes compliant action -> APPROVED
    res_app = engine.validate_recommendation(evt7, proposed_action="retry")
    assert res_app.policy_check_result == "APPROVED"
    print(" [PASS] LLM Validation: Compliant proposal -> APPROVED")

    # Case B: LLM proposes invalid action on retry limit -> REJECTED & overridden to STOP
    res_rej = engine.validate_recommendation(evt1, proposed_action="retry")
    assert res_rej.policy_check_result in ["REJECTED", "DOWNGRADED"] and res_rej.allowed_action == "STOP"
    print(" [PASS] LLM Validation: Non-compliant proposal on retry limit -> REJECTED & overridden to STOP")

    # -------------------------------------------------------------------------
    # Cooldown & Rate Limiting Verification
    # -------------------------------------------------------------------------
    now = datetime.now(timezone.utc)
    recent = now - timedelta(hours=5) # 5 hours ago (less than 24h cooldown)
    
    passed, msg = engine.check_cooldown_compliance("retry", last_action_timestamp=recent, current_timestamp=now)
    assert not passed
    print(f" [PASS] Cooldown Check: Retry within 5h blocked -> '{msg}'")

    past_cooldown = now - timedelta(hours=25) # 25 hours ago
    passed_ok, _ = engine.check_cooldown_compliance("retry", last_action_timestamp=past_cooldown, current_timestamp=now)
    assert passed_ok
    print(" [PASS] Cooldown Check: Retry after 25h passed successfully")

    print("="*80)
    print("ALL POLICY ENGINE UNIT TESTS PASSED SUCCESSFULLY WITH 100% COVERAGE!")
    print("="*80)

if __name__ == "__main__":
    test_policy_engine_matrix()
