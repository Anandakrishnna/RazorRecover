import unittest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool
from backend.api.main import app
from backend.db.session import get_session
from backend.db.models import Merchant, Customer, Transaction, RecoveryCase

class TestPhase11FastAPI(unittest.TestCase):
    def setUp(self):
        # Setup clean in-memory database with StaticPool for API test client
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        SQLModel.metadata.create_all(self.engine)

        def override_get_session():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_get_session
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_health_check(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "HEALTHY")

    def test_ingest_event_endpoint(self):
        sample_event = {
            "transaction_id": "tx_api_001",
            "customer_id": "cust_api_001",
            "merchant_id": "merch_demo_01",
            "amount": 3500.0,
            "payment_method": "card",
            "failure_type": "card_expired",
            "timestamp": "2026-09-03T10:00:00Z",
            "retry_count": 0,
            "subscription_status": "ACTIVE"
        }

        response = self.client.post("/events/ingest", json=sample_event)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["at_risk"])
        self.assertEqual(data["transaction_id"], "tx_api_001")
        self.assertIn("case_id", data)
        self.assertEqual(data["root_cause_diagnosis"]["root_cause"], "CARD_EXPIRED")
        self.assertEqual(data["agent_decision"]["policy_check_result"], "APPROVED")
        self.assertEqual(data["execution_dispatch"]["status"], "DISPATCHED")

    def test_list_cases_endpoint(self):
        # Ingest two events to populate DB
        event1 = {
            "transaction_id": "tx_api_101",
            "customer_id": "cust_101",
            "amount": 5000.0,
            "payment_method": "card",
            "failure_type": "temporary",
            "timestamp": "2026-09-03T10:00:00Z"
        }
        event2 = {
            "transaction_id": "tx_api_102",
            "customer_id": "cust_102",
            "amount": 25000.0,
            "payment_method": "card",
            "failure_type": "temporary",
            "timestamp": "2026-09-03T10:00:00Z"
        }

        self.client.post("/events/ingest", json=event1)
        self.client.post("/events/ingest", json=event2)

        response = self.client.get("/cases")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["cases"]), 2)
        # Ensure sorted by expected_recovery_value DESC
        self.assertGreaterEqual(
            data["cases"][0]["expected_recovery_value"],
            data["cases"][1]["expected_recovery_value"]
        )

    def test_get_case_detail_endpoint(self):
        event = {
            "transaction_id": "tx_api_detail_01",
            "customer_id": "cust_detail_01",
            "amount": 8000.0,
            "payment_method": "card",
            "failure_type": "temporary",
            "timestamp": "2026-09-03T10:00:00Z"
        }
        ingest_res = self.client.post("/events/ingest", json=event)
        case_id = ingest_res.json()["case_id"]

        response = self.client.get(f"/cases/{case_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["case"]["id"], case_id)
        self.assertEqual(data["transaction"]["id"], "tx_api_detail_01")
        self.assertGreater(len(data["decisions"]), 0)
        self.assertGreater(len(data["audit_log"]), 0)

    def test_get_metrics_eval_endpoint(self):
        response = self.client.get("/metrics/eval")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["heldout_events"], 200)
        self.assertGreater(data["revenue_at_risk"], 0)
        self.assertGreater(data["successfully_recovered_revenue"], 0)
        self.assertGreater(data["recovery_rate_pct"], 0)
        self.assertEqual(data["policy_violations"], 0)

if __name__ == "__main__":
    unittest.main()
