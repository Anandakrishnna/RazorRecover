import json
import math
from typing import Dict, Any, Tuple
from pydantic import BaseModel
from sqlmodel import Session
from backend.engine.audit import AuditLogger
from backend.db.models import RecoveryCase, AuditLog

class ProbabilityResult(BaseModel):
    recovery_probability: float
    expected_recovery_value: float
    risk_tier: str  # HIGH, MEDIUM, LOW
    explanation: str

class RecoveryProbabilityModel:
    """
    Explainable Tabular Recovery Probability Model.
    Predicts probability P in [0.05, 0.95] and calculates expected recovery value.
    """

    BASELINE_PROBABILITIES = {
        "temporary": 0.80,
        "network_timeout": 0.85,
        "bank_downtime": 0.85,
        "card_expired": 0.75,
        "subscription_failed": 0.65,
        "overdue_invoice": 0.55,
        "checkout_abandoned": 0.40,
        "insufficient_funds": 0.45,
    }

    def predict(self, event_dict: Dict[str, Any]) -> ProbabilityResult:
        """Predicts recovery probability and expected recovery value."""
        failure_type = event_dict.get("failure_type", "").lower()
        amount = float(event_dict.get("amount", 0.0))
        retry_count = int(event_dict.get("retry_count", 0))
        invoice_age = int(event_dict.get("invoice_age_days", 0))
        prev_outcome = event_dict.get("previous_recovery_outcome", "NONE")

        # Parse customer history
        history_raw = event_dict.get("customer_purchase_history", "{}")
        if isinstance(history_raw, str):
            try:
                history = json.loads(history_raw)
            except Exception:
                history = {}
        elif isinstance(history_raw, dict):
            history = history_raw
        else:
            history = {}

        total_orders = int(history.get("total_orders", 0))
        total_spent = float(history.get("total_spent", 0.0))

        # 1. Base Probability
        prob = self.BASELINE_PROBABILITIES.get(failure_type, 0.50)
        explanations = [f"Base probability for '{failure_type}': {prob*100:.0f}%"]

        # 2. Customer Loyalty Adjustments
        if total_orders >= 5:
            prob += 0.10
            explanations.append("Frequent customer (+10%)")
        elif total_spent >= 10000.0:
            prob += 0.10
            explanations.append("High LTV customer (+10%)")
        elif total_orders == 0:
            prob -= 0.05
            explanations.append("First-time buyer (-5%)")

        # 3. Previous Recovery Outcome Adjustments
        if prev_outcome == "RECOVERED":
            prob += 0.12
            explanations.append("Prior recovery success (+12%)")
        elif prev_outcome == "FAILED":
            prob -= 0.15
            explanations.append("Prior recovery failure (-15%)")

        # 4. Retry Count Penalty
        if retry_count > 0:
            penalty = min(0.30, retry_count * 0.15)
            prob -= penalty
            explanations.append(f"{retry_count} retries penalty (-{penalty*100:.0f}%)")

        # 5. Overdue Invoice Age Penalty
        if failure_type == "overdue_invoice":
            if invoice_age > 30:
                prob -= 0.30
                explanations.append(f"Severely overdue ({invoice_age} days) penalty (-30%)")
            elif invoice_age > 14:
                prob -= 0.15
                explanations.append(f"Overdue ({invoice_age} days) penalty (-15%)")

        # 6. High Amount Risk Dampener
        if amount >= 50000.0:
            prob -= 0.10
            explanations.append("High transaction value threshold (-10%)")

        # Hard-cap recovery probability strictly within [0.05, 0.95].
        # Floor (0.05): No recovery attempt has absolute zero chance of success.
        # Ceiling (0.95): No payment recovery intervention is 100% guaranteed due to real-world infrastructure & bank gateway variances.
        prob = round(max(0.05, min(0.95, prob)), 3)
        expected_val = round(amount * prob, 2)

        # Risk Tier Classification
        if prob >= 0.70:
            risk_tier = "HIGH_RECOVERABILITY"
        elif prob >= 0.40:
            risk_tier = "MEDIUM_RECOVERABILITY"
        else:
            risk_tier = "LOW_RECOVERABILITY"

        explanation_str = " | ".join(explanations)
        return ProbabilityResult(
            recovery_probability=prob,
            expected_recovery_value=expected_val,
            risk_tier=risk_tier,
            explanation=explanation_str
        )

    def predict_and_update_case(self, case: RecoveryCase, event_dict: Dict[str, Any], session: Session) -> ProbabilityResult:
        """Predicts probability and updates RecoveryCase in SQLite DB."""
        res = self.predict(event_dict)

        case.recovery_probability = res.recovery_probability
        case.expected_recovery_value = res.expected_recovery_value
        session.add(case)

        # Write Audit Log
        AuditLogger.log_event(
            session=session,
            case_id=case.id,
            event_type="RECOVERY_PREDICTED",
            detail_dict={
                "recovery_probability": res.recovery_probability,
                "expected_recovery_value": res.expected_recovery_value,
                "risk_tier": res.risk_tier,
                "explanation": res.explanation
            }
        )
        return res
