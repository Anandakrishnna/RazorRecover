import json
from fastapi.testclient import TestClient
from backend.api.main import app

def main():
    client = TestClient(app)

    # 1. Sample Event Payload for POST /events/ingest
    sample_payload = {
        "transaction_id": "tx_demo_77881",
        "customer_id": "cust_enterprise_09",
        "merchant_id": "merch_demo_01",
        "merchant_name": "Razorpay Demo Store",
        "customer_name": "Acme Corp",
        "amount": 28500.00,
        "payment_method": "card",
        "failure_type": "temporary",
        "timestamp": "2026-09-03T08:45:00Z",
        "retry_count": 0,
        "customer_purchase_history": json.dumps({"total_orders": 6, "total_spent": 120000.0}),
        "subscription_status": "ACTIVE",
        "checkout_behavior": "N/A",
        "invoice_age_days": 0,
        "previous_recovery_outcome": "RECOVERED"
    }

    print("================================================================================")
    print("STEP 1: POST /events/ingest")
    print("================================================================================\n")
    print(f"Request Payload:")
    print(json.dumps(sample_payload, indent=2))
    
    ingest_res = client.post("/events/ingest", json=sample_payload)
    print(f"\nResponse Status Code: {ingest_res.status_code}")
    ingest_data = ingest_res.json()
    print("Response Body:")
    print(json.dumps(ingest_data, indent=2))

    case_id = ingest_data.get("case_id")
    print(f"\nCreated Case ID: {case_id}")

    # 2. Call GET /cases
    print("\n================================================================================")
    print("STEP 2: GET /cases (List Open/All Recovery Cases)")
    print("================================================================================\n")
    
    cases_res = client.get("/cases")
    print(f"Response Status Code: {cases_res.status_code}")
    cases_data = cases_res.json()
    print("Response Body:")
    print(json.dumps(cases_data, indent=2))

    # 3. Call GET /cases/{id}
    print("\n================================================================================")
    print(f"STEP 3: GET /cases/{case_id} (Full Case Detail + Decisions + Audit Trail)")
    print("================================================================================\n")

    detail_res = client.get(f"/cases/{case_id}")
    print(f"Response Status Code: {detail_res.status_code}")
    detail_data = detail_res.json()
    print("Response Body:")
    print(json.dumps(detail_data, indent=2))

    print("\n================================================================================")
    print("API WORKFLOW DEMO COMPLETE")
    print("================================================================================")

if __name__ == "__main__":
    main()
