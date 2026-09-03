import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple, Optional
from pydantic import BaseModel
from sqlmodel import Session
from backend.db.models import RecoveryCase, AgentDecision, AuditLog
from backend.engine.audit import AuditLogger

class PolicyCheckResult(BaseModel):
    rule_id: int
    policy_action: str
    allowed_action: str
    policy_check_result: str  # APPROVED, DOWNGRADED, REJECTED
    priority_tier: str
    rationale: str
    cooldown_passed: bool = True

class PolicyEngine:
    """
    Deterministic Policy Engine implementing Section 8 Priority Ranking Matrix (First Match Wins).
    Gates all money-affecting actions regardless of LLM recommendations.
    """

    # Cooldown constraints from Section 8.5
    COOLDOWN_PAYMENT_RETRY_HOURS = 24
    RATE_LIMIT_CHECKOUT_MESSAGE_DAYS = 7
    RATE_LIMIT_INVOICE_REMINDER_DAYS = 7

    def is_high_purchase_intent(self, event_dict: Dict[str, Any], recovery_probability: float) -> bool:
        """Deterministically calculates high purchase intent per Section 8.3."""
        if recovery_probability >= 0.60:
            return True
            
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

        return total_orders >= 2 or total_spent >= 5000.0

    def check_cooldown_compliance(
        self,
        action: str,
        last_action_timestamp: Optional[datetime] = None,
        current_timestamp: Optional[datetime] = None
    ) -> Tuple[bool, str]:
        """Enforces rate limiting and cooldown rules from Section 8.5."""
        if not last_action_timestamp:
            return True, "No prior action recorded; cooldown check passed."
            
        now = current_timestamp or datetime.now(timezone.utc)
        
        # Ensure UTC timezone awareness
        if last_action_timestamp.tzinfo is None:
            last_action_timestamp = last_action_timestamp.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        elapsed = now - last_action_timestamp
        action_lower = action.lower()

        if action_lower in ["retry", "scheduled_retry_24h"]:
            if elapsed < timedelta(hours=self.COOLDOWN_PAYMENT_RETRY_HOURS):
                remaining = self.COOLDOWN_PAYMENT_RETRY_HOURS - (elapsed.total_seconds() / 3600)
                return False, f"Payment retry cooldown active ({remaining:.1f} hours remaining)."

        elif action_lower in ["send_recovery_message"]:
            if elapsed < timedelta(days=self.RATE_LIMIT_CHECKOUT_MESSAGE_DAYS):
                remaining_days = self.RATE_LIMIT_CHECKOUT_MESSAGE_DAYS - (elapsed.total_seconds() / 86400)
                return False, f"Checkout messaging rate limit active ({remaining_days:.1f} days remaining)."

        elif action_lower in ["reminder", "gentle_reminder"]:
            if elapsed < timedelta(days=self.RATE_LIMIT_INVOICE_REMINDER_DAYS):
                remaining_days = self.RATE_LIMIT_INVOICE_REMINDER_DAYS - (elapsed.total_seconds() / 86400)
                return False, f"Invoice reminder rate limit active ({remaining_days:.1f} days remaining)."

        return True, "Cooldown check passed."

    def evaluate(self, event_dict: Dict[str, Any], recovery_probability: float = 0.50) -> Tuple[int, str, str, str]:
        """
        Evaluates event against Priority Ranking Matrix in top-to-bottom order.
        Returns: (rule_id, action, priority_tier, reason)
        """
        failure_type = event_dict.get("failure_type", "").lower()
        amount = float(event_dict.get("amount", 0.0))
        retry_count = int(event_dict.get("retry_count", 0))
        invoice_age = int(event_dict.get("invoice_age_days", 0))
        payment_failures = {"temporary", "card_expired", "insufficient_funds", "network_timeout", "bank_downtime"}

        # PRIORITY 1: Safety Guardrails & Hard Stopping Rules
        if failure_type in payment_failures and retry_count >= 2:
            return 1, "STOP", "PRIORITY_1_SAFETY", f"Payment failure retry limit reached ({retry_count} retries)."

        if failure_type == "temporary" and amount >= 50000.0:
            return 2, "human_escalation", "PRIORITY_1_SAFETY", f"Temporary failure on high-value transaction (INR {amount:,.2f})."

        # PRIORITY 2: Severe Overdue & Subscription Escalations
        if failure_type == "overdue_invoice" and invoice_age > 30:
            return 3, "human_escalation", "PRIORITY_2_SEVERE", f"Invoice overdue by {invoice_age} days (> 30 days)."

        if failure_type == "subscription_failed" and retry_count >= 3:
            return 4, "pause_subscription_and_escalate", "PRIORITY_2_SEVERE", f"Subscription failure limit reached ({retry_count} retries)."

        # PRIORITY 3: Targeted Interventions
        if failure_type == "card_expired":
            return 5, "request_payment_method_update", "PRIORITY_3_TARGETED", "Expired card details require payment method update."

        if failure_type in {"insufficient_funds", "network_timeout", "bank_downtime"} and retry_count < 2:
            return 6, "scheduled_retry_24h", "PRIORITY_3_TARGETED", f"Transient infrastructure/bank failure ({failure_type}); schedule 24h retry."

        if failure_type == "temporary" and amount < 50000.0 and retry_count < 2:
            return 7, "retry", "PRIORITY_3_TARGETED", f"Temporary failure under INR 50k threshold (retry #{retry_count + 1})."

        if failure_type == "checkout_abandoned":
            high_intent = self.is_high_purchase_intent(event_dict, recovery_probability)
            if high_intent:
                return 8, "send_recovery_message", "PRIORITY_3_TARGETED", "Checkout abandoned by customer with high purchase intent."
            else:
                return 9, "log_and_suppress", "PRIORITY_3_TARGETED", "Checkout abandoned by customer with low purchase intent; suppress outreach."

        if failure_type == "subscription_failed" and retry_count < 3:
            return 10, "notify_customer_and_retry", "PRIORITY_3_TARGETED", f"Subscription billing failure (retry #{retry_count + 1}); notify customer."

        if failure_type == "overdue_invoice":
            if 7 < invoice_age <= 30:
                return 11, "reminder", "PRIORITY_3_TARGETED", f"Firm invoice reminder for {invoice_age} days overdue."
            elif invoice_age <= 7:
                return 12, "gentle_reminder", "PRIORITY_3_TARGETED", f"Gentle invoice reminder for {invoice_age} days overdue."

        # PRIORITY 4: Default Fallback Rule
        return 13, "log_and_suppress", "PRIORITY_4_FALLBACK", f"No specific policy rule matched for failure_type '{failure_type}'."

    def validate_recommendation(
        self,
        event_dict: Dict[str, Any],
        proposed_action: str,
        recovery_probability: float = 0.50,
        last_action_timestamp: Optional[datetime] = None
    ) -> PolicyCheckResult:
        """
        Validates proposed LLM recommendation against Policy Engine rule & Cooldown limits.
        Overrides non-compliant LLM recommendations.
        """
        rule_id, policy_action, tier, rationale = self.evaluate(event_dict, recovery_probability)
        proposed_norm = proposed_action.strip().lower()
        policy_norm = policy_action.strip().lower()

        # Cooldown check
        cooldown_passed, cooldown_msg = self.check_cooldown_compliance(policy_action, last_action_timestamp)

        if not cooldown_passed:
            return PolicyCheckResult(
                rule_id=rule_id,
                policy_action="log_and_suppress",
                allowed_action="log_and_suppress",
                policy_check_result="REJECTED",
                priority_tier=tier,
                rationale=f"Action '{policy_action}' blocked by cooldown: {cooldown_msg}",
                cooldown_passed=False
            )

        if proposed_norm == policy_norm:
            status = "APPROVED"
            allowed_action = policy_action
        else:
            # Overridden by Policy Engine
            status = "DOWNGRADED" if policy_norm in ["log_and_suppress", "retry", "scheduled_retry_24h"] else "REJECTED"
            allowed_action = policy_action
            rationale += f" Proposed action '{proposed_action}' overridden by Policy Rule #{rule_id}."

        return PolicyCheckResult(
            rule_id=rule_id,
            policy_action=policy_action,
            allowed_action=allowed_action,
            policy_check_result=status,
            priority_tier=tier,
            rationale=rationale,
            cooldown_passed=True
        )

    def process_and_update_case(
        self,
        case: RecoveryCase,
        event_dict: Dict[str, Any],
        proposed_action: str,
        reasoning_text: str,
        session: Session,
        last_action_timestamp: Optional[datetime] = None
    ) -> AgentDecision:
        """Evaluates policy gating and records AgentDecision & AuditLog in database."""
        result = self.validate_recommendation(
            event_dict, proposed_action, case.recovery_probability, last_action_timestamp
        )

        decision_id = f"dec_{uuid.uuid4().hex[:8]}"
        decision = AgentDecision(
            id=decision_id,
            case_id=case.id,
            recommendation=proposed_action,
            policy_check_result=result.policy_check_result,
            action_taken=result.allowed_action,
            result="PENDING",
            reasoning_text=f"[Policy Rule #{result.rule_id}] {result.rationale} | LLM Reasoning: {reasoning_text}"
        )
        session.add(decision)

        # Write Audit Log
        AuditLogger.log_event(
            session=session,
            case_id=case.id,
            event_type="POLICY_CHECK",
            detail_dict={
                "proposed_action": proposed_action,
                "allowed_action": result.allowed_action,
                "policy_check_result": result.policy_check_result,
                "rule_id": result.rule_id,
                "rationale": result.rationale,
                "cooldown_passed": result.cooldown_passed
            }
        )
        return decision
