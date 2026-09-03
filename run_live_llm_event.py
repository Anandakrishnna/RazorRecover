import os
import sys
import json
from backend.db.session import init_db
from backend.engine.agent_loop import run_agent_pipeline

def main():
    init_db()

    # Retrieve API key from CLI argument or environment
    api_key = sys.argv[1] if len(sys.argv) > 1 else os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    sample_event = {
        "transaction_id": "tx_live_llm_1001",
        "customer_id": "cust_live_77",
        "merchant_id": "merch_demo_01",
        "merchant_name": "Acme SaaS",
        "customer_name": "Jane Smith",
        "amount": 2500.00,
        "payment_method": "card",
        "failure_type": "card_expired",
        "timestamp": "2026-09-03T08:00:00Z",
        "retry_count": 0,
        "customer_purchase_history": json.dumps({"total_orders": 2, "total_spent": 5000.0}),
        "subscription_status": "ACTIVE",
        "checkout_behavior": "N/A",
        "invoice_age_days": 0,
        "previous_recovery_outcome": "NONE"
    }

    print("================================================================================")
    print("           RAZORRECOVER — LIVE GEMINI LLM RECOVERY PIPELINE TRACE               ")
    print("================================================================================\n")
    key_display = f"{api_key[:6]}...{api_key[-4:]}" if api_key else "None (Pass API key as argument)"
    print(f"Using API Key: {key_display}")
    print(f"[INCOMING EVENT Payload]:")
    print(json.dumps(sample_event, indent=2))
    print("\n--------------------------------------------------------------------------------")
    print("                     EXECUTING LIVE AGENT PIPELINE...                           ")
    print("--------------------------------------------------------------------------------\n")

    trace = run_agent_pipeline(sample_event, api_key=api_key, forced_roll=0.20, force_live=True)

    print(json.dumps(trace, indent=2))
    print("\n================================================================================")
    print("                          LIVE PIPELINE TRACE COMPLETE                          ")
    print("================================================================================")

if __name__ == "__main__":
    main()
