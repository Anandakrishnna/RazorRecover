import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from backend.db.session import engine
from backend.db.models import Merchant, Customer, Transaction, RecoveryCase, AuditLog

class RevenueEvent(BaseModel):
    transaction_id: str
    customer_id: str
    merchant_id: str = "merch_demo_01"
    merchant_name: str = "Razorpay Demo Store"
    customer_name: str = "Valued Customer"
    amount: float
    payment_method: str
    failure_type: str
    timestamp: str
    retry_count: int = 0
    retry_history: str = "[]"
    customer_purchase_history: str = "{}"
    subscription_status: str = "N/A"
    checkout_behavior: str = "N/A"
    invoice_age_days: int = 0
    previous_recovery_outcome: str = "NONE"

class RevenueMonitor:
    def __init__(self, session: Optional[Session] = None):
        self._session = session

    def is_at_risk(self, event: RevenueEvent) -> bool:
        """Determines if an incoming event represents revenue at risk."""
        at_risk_failures = {
            'temporary', 'card_expired', 'insufficient_funds', 
            'network_timeout', 'bank_downtime', 'checkout_abandoned', 
            'subscription_failed', 'overdue_invoice'
        }
        if event.failure_type in at_risk_failures:
            return True
        if event.subscription_status == 'PAST_DUE':
            return True
        if event.invoice_age_days > 0:
            return True
        return False

    def process_event(self, event_dict: Dict[str, Any], session: Optional[Session] = None) -> Tuple[bool, Optional[RecoveryCase]]:
        """
        Parses an incoming revenue event dict, checks risk status,
        and creates/persists Transaction and RecoveryCase in SQLite if at risk.
        """
        db = session or self._session
        should_close = False
        if db is None:
            db = Session(engine)
            should_close = True

        try:
            # Sanitize NaN values from CSV pandas reads
            sanitized_dict = {
                k: ("N/A" if isinstance(v, float) and v != v else v)
                for k, v in event_dict.items()
            }
            event = RevenueEvent(**sanitized_dict)
            
            if not self.is_at_risk(event):
                return False, None

            # 1. Upsert Merchant
            merchant = db.get(Merchant, event.merchant_id)
            if not merchant:
                merchant = Merchant(id=event.merchant_id, name=event.merchant_name)
                db.add(merchant)
                db.flush()

            # 2. Upsert Customer
            customer = db.get(Customer, event.customer_id)
            if not customer:
                customer = Customer(
                    id=event.customer_id,
                    merchant_id=event.merchant_id,
                    name=event.customer_name,
                    subscription_status=event.subscription_status,
                    previous_recovery_outcome=event.previous_recovery_outcome,
                    history_json=event.customer_purchase_history
                )
                db.add(customer)
            else:
                customer.subscription_status = event.subscription_status
                customer.previous_recovery_outcome = event.previous_recovery_outcome
                customer.history_json = event.customer_purchase_history
                db.add(customer)
            db.flush()

            # 3. Upsert Transaction
            transaction = db.get(Transaction, event.transaction_id)
            if not transaction:
                transaction = Transaction(
                    id=event.transaction_id,
                    merchant_id=event.merchant_id,
                    customer_id=event.customer_id,
                    amount=event.amount,
                    method=event.payment_method,
                    status="FAILED",
                    failure_type=event.failure_type,
                    retry_count=event.retry_count,
                    checkout_behavior=event.checkout_behavior,
                    invoice_age_days=event.invoice_age_days,
                    retry_history_json=event.retry_history
                )
                db.add(transaction)
            else:
                transaction.amount = event.amount
                transaction.retry_count = event.retry_count
                transaction.failure_type = event.failure_type
                transaction.invoice_age_days = event.invoice_age_days
                db.add(transaction)
            db.flush()

            # 4. Check for existing case or create new Case
            statement = select(RecoveryCase).where(RecoveryCase.transaction_id == event.transaction_id)
            existing_case = db.exec(statement).first()
            
            if existing_case:
                case = existing_case
            else:
                case_id = f"case_{uuid.uuid4().hex[:8]}"
                case = RecoveryCase(
                    id=case_id,
                    transaction_id=event.transaction_id,
                    revenue_at_risk=event.amount,
                    root_cause="UNCLASSIFIED",
                    confidence=0.0,
                    recovery_probability=0.0,
                    expected_recovery_value=0.0,
                    status="OPEN",
                    opened_at=datetime.now(timezone.utc)
                )
                db.add(case)
                db.flush()

                # Audit Log
                audit = AuditLog(
                    id=f"audit_{uuid.uuid4().hex[:8]}",
                    case_id=case.id,
                    event_type="EVENT_INGESTED",
                    detail_json=f'{{"transaction_id": "{event.transaction_id}", "amount": {event.amount}, "failure_type": "{event.failure_type}"}}'
                )
                db.add(audit)

            if should_close:
                db.commit()
                db.refresh(case)
            else:
                db.flush()
            return True, case

        finally:
            if should_close:
                db.close()
