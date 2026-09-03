import random
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel
from sqlmodel import Session
from backend.db.models import RecoveryCase, AgentDecision
from backend.engine.audit import AuditLogger
from backend.engine.policy_engine import PolicyEngine

class VerificationResult(BaseModel):
    case_id: str
    status: str  # RECOVERED, FAILED, ESCALATED, STOPPED
    decision_result: str  # SUCCESS, FAILED, ESCALATED, STOPPED, SUPPRESSED
    success_rate_probability: float
    roll: float
    recovered_amount: float
    verification_notes: str
    closed_at: str

class VerifierEngine:
    """
    Verifier Engine component for RazorRecover agent loop.
    Evaluates action outcomes based on Section 10.1 synthetic transition probabilities.
    Updates RecoveryCase status, closed_at timestamp, AgentDecision result, and writes audit logs.
    """

    def __init__(self):
        self.policy_engine = PolicyEngine()

    def determine_success_probability(
        self,
        action: str,
        event_dict: Dict[str, Any],
        recovery_probability: float = 0.50
    ) -> Tuple[float, str]:
        """
        Determines the transition probability per Section 10.1 PRD rules.
        Returns: (success_rate_probability, rationale)
        """
        action_clean = action.strip().lower()
        retry_count = int(event_dict.get("retry_count", 0))

        # 1. Card Expiration Update -> 70%
        if action_clean == "request_payment_method_update":
            return 0.70, "Section 10.1: Card expiration update link outreach has 70% success rate."

        # 2. Temporary Payment Retries -> 80% (1st retry), 40% (2nd retry)
        elif action_clean in ["retry", "scheduled_retry_24h", "notify_customer_and_retry"]:
            if retry_count == 0:
                return 0.80, "Section 10.1: 1st temporary payment retry has 80% success rate."
            elif retry_count == 1:
                return 0.40, "Section 10.1: 2nd temporary payment retry has 40% success rate."
            else:
                return 0.10, "Repeated payment retries (>2) have diminishing success rate (10%)."

        # 3. Abandoned Checkout Recovery Messages -> 35% for High Intent
        elif action_clean == "send_recovery_message":
            is_high_intent = self.policy_engine.is_high_purchase_intent(event_dict, recovery_probability)
            if is_high_intent:
                return 0.35, "Section 10.1: Abandoned checkout message for high purchase intent has 35% conversion."
            else:
                return 0.10, "Abandoned checkout message for low purchase intent has 10% conversion."

        # 4. Overdue Invoice Reminders
        elif action_clean == "gentle_reminder":
            return 0.50, "Gentle invoice reminder has 50% recovery probability."
        elif action_clean == "reminder":
            return 0.45, "Firm invoice reminder has 45% recovery probability."

        # 5. Non-payment actions (Escalation / Suppress)
        elif action_clean in ["human_escalation", "pause_subscription_and_escalate"]:
            return 0.0, "Case escalated to human operator; pending external manual resolution."
        elif action_clean in ["log_and_suppress", "stop"]:
            return 0.0, "Action suppressed or capped by policy stopping rule."
        else:
            return 0.30, f"Default outcome probability for action '{action}' is 30%."

    def verify_outcome(
        self,
        case: RecoveryCase,
        decision: AgentDecision,
        event_dict: Dict[str, Any],
        session: Session,
        seed: Optional[int] = None,
        forced_roll: Optional[float] = None
    ) -> VerificationResult:
        """
        Executes outcome verification roll, updates RecoveryCase status & closed_at,
        updates AgentDecision result, and logs audit record.
        """
        action = decision.action_taken.strip()
        action_clean = action.lower()
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # Handle Escalation & Suppression explicitly
        if action_clean in ["human_escalation", "pause_subscription_and_escalate"]:
            case.status = "ESCALATED"
            case.closed_at = None  # Remains open in operator escalation queue
            decision.result = "ESCALATED"
            session.add(case)
            session.add(decision)

            res = VerificationResult(
                case_id=case.id,
                status="ESCALATED",
                decision_result="ESCALATED",
                success_rate_probability=0.0,
                roll=0.0,
                recovered_amount=0.0,
                verification_notes="Case successfully placed into Escalation queue for human operator review.",
                closed_at="N/A (ESCALATED)"
            )

            AuditLogger.log_event(
                session=session,
                case_id=case.id,
                event_type="ESCALATED",
                detail_dict={
                    "status": "ESCALATED",
                    "action_taken": action,
                    "revenue_at_risk": case.revenue_at_risk
                }
            )
            session.flush()
            return res

        elif action_clean in ["log_and_suppress", "stop"]:
            case.status = "STOPPED"
            case.closed_at = now
            decision.result = "STOPPED" if action_clean == "stop" else "SUPPRESSED"
            session.add(case)
            session.add(decision)

            res = VerificationResult(
                case_id=case.id,
                status="STOPPED",
                decision_result=decision.result,
                success_rate_probability=0.0,
                roll=0.0,
                recovered_amount=0.0,
                verification_notes=f"Case closed as STOPPED ({action}). No recovery attempted.",
                closed_at=now_iso
            )

            AuditLogger.log_event(
                session=session,
                case_id=case.id,
                event_type="STOPPED",
                detail_dict={
                    "status": "STOPPED",
                    "action_taken": action,
                    "revenue_at_risk": case.revenue_at_risk
                }
            )
            session.flush()
            return res

        # Standard Probabilistic Verification Roll
        success_prob, rationale = self.determine_success_probability(
            action=action,
            event_dict=event_dict,
            recovery_probability=case.recovery_probability
        )

        if forced_roll is not None:
            roll = forced_roll
        else:
            if seed is not None:
                rng = random.Random(seed)
                roll = rng.random()
            else:
                roll = random.random()

        is_success = roll < success_prob

        if is_success:
            case.status = "RECOVERED"
            case.closed_at = now
            decision.result = "SUCCESS"
            recovered_amount = case.revenue_at_risk
            verification_notes = f"VERIFIED RECOVERED: Roll {roll:.4f} < Success Rate {success_prob:.2f}. {rationale}"
        else:
            case.status = "FAILED"
            case.closed_at = now
            decision.result = "FAILED"
            recovered_amount = 0.0
            verification_notes = f"VERIFICATION FAILED: Roll {roll:.4f} >= Success Rate {success_prob:.2f}. {rationale}"

        session.add(case)
        session.add(decision)

        res = VerificationResult(
            case_id=case.id,
            status=case.status,
            decision_result=decision.result,
            success_rate_probability=success_prob,
            roll=round(roll, 4),
            recovered_amount=recovered_amount,
            verification_notes=verification_notes,
            closed_at=now_iso
        )

        # Log VERIFIED audit log entry
        AuditLogger.log_event(
            session=session,
            case_id=case.id,
            event_type="VERIFIED",
            detail_dict={
                "status": case.status,
                "decision_result": decision.result,
                "success_probability": success_prob,
                "roll": round(roll, 4),
                "recovered_amount": recovered_amount,
                "notes": verification_notes
            }
        )
        session.flush()
        return res
