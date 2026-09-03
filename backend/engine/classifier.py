import json
import uuid
from typing import Dict, Any, Tuple, Optional
from pydantic import BaseModel
from sqlmodel import Session
from backend.db.models import RecoveryCase, AuditLog

class ClassificationResult(BaseModel):
    root_cause: str
    confidence: float
    reasoning: str

class RootCauseClassifier:
    """
    Hybrid Root Cause Classifier combining deterministic rule matching
    with configurable confidence scoring.
    """

    CAUSE_TAXONOMY = {
        "CARD_EXPIRED": "Payment card expired or details invalid.",
        "NETWORK_TIMEOUT": "Temporary network timeout, gateway issue, or bank downtime.",
        "INSUFFICIENT_FUNDS": "Account or card balance insufficient.",
        "INTENT_ABANDONED": "Checkout session abandoned by customer before payment completion.",
        "SUBSCRIPTION_LAPSED": "Recurring subscription billing authorization failed.",
        "OVERDUE_INVOICE": "B2B invoice unpaid past credit terms.",
        "UNRECOVERABLE_DECLINE": "Hard decline by issuing bank or account blocked."
    }

    def classify(self, event_dict: Dict[str, Any]) -> ClassificationResult:
        """Classifies root cause and calculates confidence score."""
        failure_type = event_dict.get("failure_type", "").lower()
        amount = float(event_dict.get("amount", 0.0))
        retry_count = int(event_dict.get("retry_count", 0))
        method = event_dict.get("payment_method", "").lower()
        invoice_age = int(event_dict.get("invoice_age_days", 0))

        # 1. Deterministic Rule Matching
        if failure_type == "card_expired":
            return ClassificationResult(
                root_cause="CARD_EXPIRED",
                confidence=0.98,
                reasoning=f"Direct failure code '{failure_type}' indicates expired card credentials for payment method '{method}'."
            )

        elif failure_type in ["temporary", "network_timeout", "bank_downtime"]:
            confidence = 0.92 if failure_type in ["network_timeout", "bank_downtime"] else 0.88
            if retry_count > 0:
                confidence -= (retry_count * 0.05) # Slight confidence reduction on repeated retries
            return ClassificationResult(
                root_cause="NETWORK_TIMEOUT",
                confidence=round(max(0.70, confidence), 2),
                reasoning=f"Transient infrastructure failure '{failure_type}' observed after {retry_count} retries."
            )

        elif failure_type == "insufficient_funds":
            return ClassificationResult(
                root_cause="INSUFFICIENT_FUNDS",
                confidence=0.94,
                reasoning=f"Bank response code '{failure_type}' for transaction amount INR {amount}."
            )

        elif failure_type == "checkout_abandoned":
            behavior = event_dict.get("checkout_behavior", "N/A")
            return ClassificationResult(
                root_cause="INTENT_ABANDONED",
                confidence=0.95 if behavior == "abandoned_at_payment" else 0.90,
                reasoning=f"User session ended abruptly during checkout ({behavior})."
            )

        elif failure_type == "subscription_failed":
            return ClassificationResult(
                root_cause="SUBSCRIPTION_LAPSED",
                confidence=0.93,
                reasoning=f"Recurring subscription authorization failure after {retry_count} automated attempts."
            )

        elif failure_type == "overdue_invoice":
            return ClassificationResult(
                root_cause="OVERDUE_INVOICE",
                confidence=0.96,
                reasoning=f"B2B invoice remains unpaid for {invoice_age} days."
            )

        else:
            return ClassificationResult(
                root_cause="UNRECOVERABLE_DECLINE",
                confidence=0.60,
                reasoning=f"Unrecognized or unclassified failure type '{failure_type}' defaulted to hard decline."
            )

    def classify_and_update_case(self, case: RecoveryCase, event_dict: Dict[str, Any], session: Session) -> ClassificationResult:
        """Classifies event root cause and updates RecoveryCase record in database."""
        res = self.classify(event_dict)
        
        case.root_cause = res.root_cause
        case.confidence = res.confidence
        session.add(case)
        
        # Write Audit Log
        audit = AuditLog(
            id=f"audit_{uuid.uuid4().hex[:8]}",
            case_id=case.id,
            event_type="CLASSIFIED",
            detail_json=json.dumps({
                "root_cause": res.root_cause,
                "confidence": res.confidence,
                "reasoning": res.reasoning
            })
        )
        session.add(audit)
        session.flush()
        return res
