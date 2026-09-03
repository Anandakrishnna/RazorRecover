import json
import random
from datetime import datetime, timedelta, timezone
import pandas as pd

def generate_events(total_events: int = 1000, seed: int = 42):
    random.seed(seed)
    
    events = []
    start_time = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
    
    # 40% temporary (400), 20% card/method issues (200), 20% checkout abandonment (200), 
    # 10% subscription failures (100), 10% overdue invoices (100)
    categories = (
        ['temporary'] * int(total_events * 0.40) +
        ['card_method_issue'] * int(total_events * 0.20) +
        ['checkout_abandoned'] * int(total_events * 0.20) +
        ['subscription_failed'] * int(total_events * 0.10) +
        ['overdue_invoice'] * int(total_events * 0.10)
    )
    random.shuffle(categories)
    
    card_issues = ['card_expired', 'insufficient_funds', 'network_timeout', 'bank_downtime']
    payment_methods = ['card', 'upi', 'netbanking', 'invoice']
    subscription_statuses = ['ACTIVE', 'PAST_DUE', 'PAUSED', 'CANCELLED']
    checkout_behaviors = ['abandoned_at_payment', 'abandoned_at_cart']
    previous_outcomes = ['RECOVERED', 'FAILED', 'NONE']
    
    for i in range(total_events):
        txn_id = f"txn_{i+1:04d}"
        cust_id = f"cust_{random.randint(1, 150):03d}"
        cat = categories[i]
        
        # Determine specific failure_type
        if cat == 'temporary':
            failure_type = 'temporary'
        elif cat == 'card_method_issue':
            failure_type = random.choice(card_issues)
        elif cat == 'checkout_abandoned':
            failure_type = 'checkout_abandoned'
        elif cat == 'subscription_failed':
            failure_type = 'subscription_failed'
        else: # overdue_invoice
            failure_type = 'overdue_invoice'
            
        # Amount distribution by failure type
        if failure_type == 'overdue_invoice':
            amount = round(random.uniform(5000.0, 85000.0), 2)
            method = 'invoice'
            invoice_age_days = random.randint(1, 45)
            subscription_status = 'N/A'
            checkout_behavior = 'N/A'
        elif failure_type == 'subscription_failed':
            amount = round(random.choice([499.0, 999.0, 1999.0, 4999.0, 9999.0]), 2)
            method = random.choice(['card', 'upi'])
            invoice_age_days = 0
            subscription_status = random.choice(['PAST_DUE', 'ACTIVE'])
            checkout_behavior = 'N/A'
        elif failure_type == 'checkout_abandoned':
            amount = round(random.uniform(200.0, 15000.0), 2)
            method = random.choice(['card', 'upi', 'netbanking'])
            invoice_age_days = 0
            subscription_status = 'ACTIVE'
            checkout_behavior = random.choice(checkout_behaviors)
        else: # payment failure (temporary, card_expired, insufficient_funds, etc.)
            amount = round(random.uniform(100.0, 60000.0), 2)
            method = random.choice(['card', 'upi', 'netbanking'])
            invoice_age_days = 0
            subscription_status = 'ACTIVE'
            checkout_behavior = 'N/A'

        # Retry history
        if failure_type == 'temporary':
            retry_count = random.choice([0, 1, 2])
        elif failure_type == 'subscription_failed':
            retry_count = random.choice([0, 1, 2, 3])
        else:
            retry_count = 0
            
        retry_history = [
            {"retry_num": r + 1, "status": "FAILED", "timestamp": (start_time + timedelta(hours=r*24)).isoformat()}
            for r in range(retry_count)
        ]
        
        # Customer purchase history
        orders_count = random.randint(0, 15)
        spent_total = round(orders_count * random.uniform(500, 3000), 2)
        history_json = {
            "total_orders": orders_count,
            "total_spent": spent_total,
            "last_order_days_ago": random.randint(2, 60)
        }
        
        prev_outcome = random.choice(previous_outcomes) if orders_count > 0 else 'NONE'
        
        # Event timestamp
        time_offset = timedelta(days=random.randint(0, 30), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        event_time = (start_time + time_offset).isoformat()
        
        # Ground truth recovery determination for evaluation
        if failure_type == 'card_expired':
            is_recoverable = True
            ground_truth_cause = 'CARD_EXPIRED'
        elif failure_type == 'temporary':
            is_recoverable = (amount < 50000.0 and retry_count < 2)
            ground_truth_cause = 'NETWORK_TIMEOUT'
        elif failure_type == 'checkout_abandoned':
            is_recoverable = (orders_count >= 2 or spent_total >= 5000.0)
            ground_truth_cause = 'INTENT_ABANDONED'
        elif failure_type == 'subscription_failed':
            is_recoverable = (retry_count < 3)
            ground_truth_cause = 'SUBSCRIPTION_LAPSED'
        elif failure_type == 'overdue_invoice':
            is_recoverable = (invoice_age_days <= 30)
            ground_truth_cause = 'OVERDUE_INVOICE'
        else:
            is_recoverable = random.choice([True, False])
            ground_truth_cause = failure_type.upper()

        events.append({
            "transaction_id": txn_id,
            "customer_id": cust_id,
            "amount": amount,
            "payment_method": method,
            "failure_type": failure_type,
            "timestamp": event_time,
            "retry_count": retry_count,
            "retry_history": json.dumps(retry_history),
            "customer_purchase_history": json.dumps(history_json),
            "subscription_status": subscription_status,
            "checkout_behavior": checkout_behavior,
            "invoice_age_days": invoice_age_days,
            "previous_recovery_outcome": prev_outcome,
            "is_recoverable": is_recoverable,
            "ground_truth_cause": ground_truth_cause
        })
        
    df = pd.DataFrame(events)
    
    # Dev / Holdout Split (800 / 200)
    dev_df = df.iloc[:800]
    holdout_df = df.iloc[800:]
    
    dev_df.to_csv("data/events_dev.csv", index=False)
    holdout_df.to_csv("data/events_holdout.csv", index=False)
    
    print(f"Generated {len(df)} total events:")
    print(f" - Saved {len(dev_df)} events to data/events_dev.csv")
    print(f" - Saved {len(holdout_df)} events to data/events_holdout.csv")
    print("\nFailure Type Distribution:")
    print(df['failure_type'].value_counts())

if __name__ == "__main__":
    generate_events(1000)
