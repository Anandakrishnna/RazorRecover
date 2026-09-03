import unittest
from sqlmodel import Session, SQLModel, create_engine, select
from backend.db.models import Merchant, Customer, Transaction, RecoveryCase, AgentDecision, AuditLog
from backend.engine import (
    RevenueMonitor,
    RootCauseClassifier,
    RecoveryProbabilityModel,
    PolicyEngine,
    LLMRecommender,
    ToolExecutor,
    VerifierEngine,
    AuditLogger,
    run_agent_pipeline
)

class TestPhase8Phase9Phase10(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self):
        self.session.close()

    def test_executor_payment_dispatched(self):
        executor = ToolExecutor()
        case = RecoveryCase(
            id="case_test_01",
            transaction_id="tx_01",
            revenue_at_risk=1500.0,
            root_cause="CARD_EXPIRED",
            confidence=0.98,
            recovery_probability=0.75,
            expected_recovery_value=1125.0,
            status="OPEN"
        )
        decision = AgentDecision(
            id="dec_01",
            case_id="case_test_01",
            recommendation="request_payment_method_update",
            policy_check_result="APPROVED",
            action_taken="request_payment_method_update",
            result="PENDING",
            reasoning_text="Card update requested."
        )
        self.session.add(case)
        self.session.add(decision)
        self.session.commit()

        event = {"transaction_id": "tx_01", "customer_id": "cust_01", "amount": 1500.0}
        res = executor.execute_action(case, decision, event, self.session)

        self.assertEqual(res.status, "DISPATCHED")
        self.assertEqual(res.tool, "payment_api")
        self.assertEqual(res.action, "request_payment_method_update")
        self.assertTrue(res.dispatch_id.startswith("pay_mock_"))

        # Check Audit Log
        logs = self.session.exec(select(AuditLog).where(AuditLog.case_id == "case_test_01")).all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].event_type, "ACTION_EXECUTED")

    def test_executor_messaging_dispatched(self):
        executor = ToolExecutor()
        case = RecoveryCase(
            id="case_test_02",
            transaction_id="tx_02",
            revenue_at_risk=2500.0,
            root_cause="INTENT_ABANDONED",
            confidence=0.95,
            recovery_probability=0.65,
            expected_recovery_value=1625.0,
            status="OPEN"
        )
        decision = AgentDecision(
            id="dec_02",
            case_id="case_test_02",
            recommendation="send_recovery_message",
            policy_check_result="APPROVED",
            action_taken="send_recovery_message",
            result="PENDING",
            reasoning_text="Abandoned checkout outreach."
        )
        self.session.add(case)
        self.session.add(decision)
        self.session.commit()

        event = {"transaction_id": "tx_02", "customer_id": "cust_02", "amount": 2500.0}
        res = executor.execute_action(case, decision, event, self.session)

        self.assertEqual(res.status, "DISPATCHED")
        self.assertEqual(res.tool, "messaging_api")
        self.assertEqual(res.action, "send_recovery_message")

    def test_executor_escalation_dispatched(self):
        executor = ToolExecutor()
        case = RecoveryCase(
            id="case_test_03",
            transaction_id="tx_03",
            revenue_at_risk=60000.0,
            root_cause="NETWORK_TIMEOUT",
            confidence=0.90,
            recovery_probability=0.70,
            expected_recovery_value=42000.0,
            status="OPEN"
        )
        decision = AgentDecision(
            id="dec_03",
            case_id="case_test_03",
            recommendation="human_escalation",
            policy_check_result="APPROVED",
            action_taken="human_escalation",
            result="PENDING",
            reasoning_text="High transaction value escalation."
        )
        self.session.add(case)
        self.session.add(decision)
        self.session.commit()

        event = {"transaction_id": "tx_03", "customer_id": "cust_03", "amount": 60000.0}
        res = executor.execute_action(case, decision, event, self.session)

        self.assertEqual(res.status, "DISPATCHED")
        self.assertEqual(res.tool, "escalation_api")
        self.assertEqual(res.action, "human_escalation")

    def test_verifier_probabilistic_success(self):
        verifier = VerifierEngine()
        case = RecoveryCase(
            id="case_verif_01",
            transaction_id="tx_v1",
            revenue_at_risk=2000.0,
            root_cause="CARD_EXPIRED",
            confidence=0.98,
            recovery_probability=0.75,
            expected_recovery_value=1500.0,
            status="OPEN"
        )
        decision = AgentDecision(
            id="dec_v1",
            case_id="case_verif_01",
            recommendation="request_payment_method_update",
            policy_check_result="APPROVED",
            action_taken="request_payment_method_update",
            result="PENDING",
            reasoning_text="Request card update."
        )
        self.session.add(case)
        self.session.add(decision)
        self.session.commit()

        event = {"transaction_id": "tx_v1", "retry_count": 0}
        # Force roll = 0.50 (Success because 0.50 < 0.70)
        res = verifier.verify_outcome(case, decision, event, self.session, forced_roll=0.50)

        self.assertEqual(res.status, "RECOVERED")
        self.assertEqual(res.decision_result, "SUCCESS")
        self.assertEqual(res.recovered_amount, 2000.0)
        self.assertEqual(case.status, "RECOVERED")
        self.assertIsNotNone(case.closed_at)
        self.assertEqual(decision.result, "SUCCESS")

    def test_verifier_probabilistic_failure(self):
        verifier = VerifierEngine()
        case = RecoveryCase(
            id="case_verif_02",
            transaction_id="tx_v2",
            revenue_at_risk=2000.0,
            root_cause="CARD_EXPIRED",
            confidence=0.98,
            recovery_probability=0.75,
            expected_recovery_value=1500.0,
            status="OPEN"
        )
        decision = AgentDecision(
            id="dec_v2",
            case_id="case_verif_02",
            recommendation="request_payment_method_update",
            policy_check_result="APPROVED",
            action_taken="request_payment_method_update",
            result="PENDING",
            reasoning_text="Request card update."
        )
        self.session.add(case)
        self.session.add(decision)
        self.session.commit()

        event = {"transaction_id": "tx_v2", "retry_count": 0}
        # Force roll = 0.85 (Failed because 0.85 >= 0.70)
        res = verifier.verify_outcome(case, decision, event, self.session, forced_roll=0.85)

        self.assertEqual(res.status, "FAILED")
        self.assertEqual(res.decision_result, "FAILED")
        self.assertEqual(res.recovered_amount, 0.0)
        self.assertEqual(case.status, "FAILED")
        self.assertIsNotNone(case.closed_at)

    def test_verifier_escalated_status(self):
        verifier = VerifierEngine()
        case = RecoveryCase(
            id="case_verif_03",
            transaction_id="tx_v3",
            revenue_at_risk=75000.0,
            root_cause="NETWORK_TIMEOUT",
            confidence=0.90,
            recovery_probability=0.70,
            expected_recovery_value=52500.0,
            status="OPEN"
        )
        decision = AgentDecision(
            id="dec_v3",
            case_id="case_verif_03",
            recommendation="human_escalation",
            policy_check_result="APPROVED",
            action_taken="human_escalation",
            result="PENDING",
            reasoning_text="High value transaction safety cap."
        )
        self.session.add(case)
        self.session.add(decision)
        self.session.commit()

        event = {"transaction_id": "tx_v3", "amount": 75000.0}
        res = verifier.verify_outcome(case, decision, event, self.session)

        self.assertEqual(res.status, "ESCALATED")
        self.assertEqual(case.status, "ESCALATED")

    def test_full_agent_pipeline(self):
        sample_event = {
            "transaction_id": "tx_e2e_001",
            "customer_id": "cust_e2e_001",
            "merchant_id": "merch_demo_01",
            "amount": 4999.0,
            "payment_method": "card",
            "failure_type": "temporary",
            "timestamp": "2026-09-03T10:00:00Z",
            "retry_count": 0,
            "customer_purchase_history": '{"total_orders": 3, "total_spent": 12500.0}',
            "subscription_status": "ACTIVE",
            "previous_recovery_outcome": "RECOVERED"
        }

        # Run full pipeline with forced_roll=0.30 (Success for retry since 80% success rate)
        trace = run_agent_pipeline(sample_event, session=self.session, forced_roll=0.30)

        self.assertTrue(trace["at_risk"])
        self.assertEqual(trace["transaction_id"], "tx_e2e_001")
        self.assertEqual(trace["root_cause_diagnosis"]["root_cause"], "NETWORK_TIMEOUT")
        self.assertEqual(trace["agent_decision"]["policy_check_result"], "APPROVED")
        self.assertEqual(trace["execution_dispatch"]["status"], "DISPATCHED")
        self.assertEqual(trace["execution_dispatch"]["tool"], "payment_api")
        self.assertEqual(trace["verification_result"]["status"], "RECOVERED")
        self.assertEqual(trace["final_case_status"], "RECOVERED")

        # Check complete audit trail
        self.assertEqual(len(trace["audit_trail"]), 6)
        event_types = [a["event_type"] for a in trace["audit_trail"]]
        self.assertIn("EVENT_INGESTED", event_types)
        self.assertIn("CLASSIFIED", event_types)
        self.assertIn("RECOVERY_PREDICTED", event_types)
        self.assertIn("POLICY_CHECK", event_types)
        self.assertIn("ACTION_EXECUTED", event_types)
        self.assertIn("VERIFIED", event_types)

if __name__ == "__main__":
    unittest.main()
