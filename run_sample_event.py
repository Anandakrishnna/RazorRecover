import json
from backend.db.session import engine, init_db
from backend.engine.agent_loop import run_agent_pipeline

def main():
    # Ensure database and tables exist
    init_db()


    # Sample Event: Temporary Payment Failure on active customer
    sample_event = {
        "transaction_id": "tx_sample_99182",
        "customer_id": "cust_acme_88",
        "merchant_id": "merch_demo_01",
        "merchant_name": "Acme SaaS Solutions",
        "customer_name": "John Doe",
        "amount": 14999.00,
        "payment_method": "card",
        "failure_type": "temporary",
        "timestamp": "2026-09-03T07:55:00Z",
        "retry_count": 0,
        "customer_purchase_history": json.dumps({"total_orders": 4, "total_spent": 45000.0}),
        "subscription_status": "ACTIVE",
        "checkout_behavior": "N/A",
        "invoice_age_days": 0,
        "previous_recovery_outcome": "RECOVERED"
    }

    print("================================================================================")
    print("               RAZORRECOVER — AUTONOMOUS REVENUE RECOVERY AGENT                 ")
    print("                          END-TO-END PIPELINE TRACE                             ")
    print("================================================================================\n")
    print(f"[INCOMING EVENT Payload]:")
    print(json.dumps(sample_event, indent=2))
    print("\n--------------------------------------------------------------------------------")
    print("                     EXECUTING AGENT PIPELINE STAGES...                         ")
    print("--------------------------------------------------------------------------------\n")

    # Run agent pipeline
    trace = run_agent_pipeline(sample_event, seed=42)

    print(json.dumps(trace, indent=2))
    print("\n================================================================================")
    print("                          PIPELINE EXECUTION COMPLETE                           ")
    print("================================================================================")

if __name__ == "__main__":
    main()
