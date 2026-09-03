import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel
from sqlmodel import Session
from backend.db.models import RecoveryCase, AgentDecision
from backend.engine.audit import AuditLogger

class ExecutionResult(BaseModel):
    status: str  # DISPATCHED, SUPPRESSED, REJECTED
    tool: str  # payment_api, messaging_api, escalation_api, none
    action: str
    dispatch_id: str
    details: Dict[str, Any]
    timestamp: str

class ToolExecutor:
    """
    Tool Executor component for RazorRecover agent loop.
    Executes bounded, simulated tool actions for Payment, Messaging, and Escalation APIs.
    Returns simulated {"status": "DISPATCHED"} responses and writes ACTION_EXECUTED audit logs.
    """

    PAYMENT_ACTIONS = {"retry", "scheduled_retry_24h", "request_payment_method_update"}
    MESSAGING_ACTIONS = {"send_recovery_message", "reminder", "gentle_reminder", "notify_customer_and_retry"}
    ESCALATION_ACTIONS = {"human_escalation", "pause_subscription_and_escalate"}
    SUPPRESS_ACTIONS = {"log_and_suppress", "STOP"}

    def _execute_payment_api(self, action: str, case: RecoveryCase, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Simulated Payment API Mock."""
        dispatch_id = f"pay_mock_{uuid.uuid4().hex[:8]}"
        amount = event_dict.get("amount", case.revenue_at_risk)
        method = event_dict.get("payment_method", "card")

        if action in ["retry", "scheduled_retry_24h"]:
            detail_msg = f"Simulated payment retry dispatched for transaction {case.transaction_id} (INR {amount} via {method})."
        elif action == "request_payment_method_update":
            detail_msg = f"Simulated payment method update link generated & sent for customer {event_dict.get('customer_id')}."
        else:
            detail_msg = f"Simulated payment action '{action}' executed."

        return {
            "dispatch_id": dispatch_id,
            "tool": "payment_api",
            "message": detail_msg,
            "simulated_http_code": 200
        }

    def _execute_messaging_api(self, action: str, case: RecoveryCase, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Simulated Messaging API Mock (WhatsApp / Email)."""
        dispatch_id = f"msg_mock_{uuid.uuid4().hex[:8]}"
        customer_id = event_dict.get("customer_id", "cust_unknown")
        
        if action == "send_recovery_message":
            channel = "WhatsApp"
            detail_msg = f"Simulated recovery message with 1-click checkout dispatched to customer {customer_id} via {channel}."
        elif action in ["reminder", "gentle_reminder"]:
            channel = "Email"
            detail_msg = f"Simulated invoice reminder ({action}) dispatched to customer {customer_id} via {channel}."
        elif action == "notify_customer_and_retry":
            channel = "Email+SMS"
            detail_msg = f"Simulated subscription failure notification dispatched to customer {customer_id} via {channel}."
        else:
            channel = "Email"
            detail_msg = f"Simulated messaging action '{action}' dispatched."

        return {
            "dispatch_id": dispatch_id,
            "tool": "messaging_api",
            "channel": channel,
            "message": detail_msg,
            "simulated_http_code": 200
        }

    def _execute_escalation_api(self, action: str, case: RecoveryCase, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Simulated Escalation API Mock (Ticket Creation for Human Ops)."""
        dispatch_id = f"tkt_mock_{uuid.uuid4().hex[:8]}"
        amount = event_dict.get("amount", case.revenue_at_risk)

        if action == "human_escalation":
            detail_msg = f"High-value / severe case (INR {amount}) escalated to human operations queue. Ticket #{dispatch_id} created."
        elif action == "pause_subscription_and_escalate":
            detail_msg = f"Subscription paused after max retries. Case escalated to merchant support team. Ticket #{dispatch_id} created."
        else:
            detail_msg = f"Simulated escalation ticket #{dispatch_id} created."

        return {
            "dispatch_id": dispatch_id,
            "tool": "escalation_api",
            "priority": "HIGH" if amount >= 50000.0 else "MEDIUM",
            "message": detail_msg,
            "simulated_http_code": 201
        }

    def execute_action(
        self,
        case: RecoveryCase,
        decision: AgentDecision,
        event_dict: Dict[str, Any],
        session: Session
    ) -> ExecutionResult:
        """
        Executes the allowed policy action for a case, logs audit event, and returns ExecutionResult.
        """
        action = decision.action_taken.strip()
        now_iso = datetime.now(timezone.utc).isoformat()

        if action in self.SUPPRESS_ACTIONS:
            result = ExecutionResult(
                status="SUPPRESSED",
                tool="none",
                action=action,
                dispatch_id="none",
                details={
                    "message": f"Action '{action}' logged and suppressed. No active dispatch executed.",
                    "policy_result": decision.policy_check_result
                },
                timestamp=now_iso
            )
        elif action in self.PAYMENT_ACTIONS:
            details = self._execute_payment_api(action, case, event_dict)
            result = ExecutionResult(
                status="DISPATCHED",
                tool="payment_api",
                action=action,
                dispatch_id=details["dispatch_id"],
                details=details,
                timestamp=now_iso
            )
        elif action in self.MESSAGING_ACTIONS:
            details = self._execute_messaging_api(action, case, event_dict)
            result = ExecutionResult(
                status="DISPATCHED",
                tool="messaging_api",
                action=action,
                dispatch_id=details["dispatch_id"],
                details=details,
                timestamp=now_iso
            )
        elif action in self.ESCALATION_ACTIONS:
            details = self._execute_escalation_api(action, case, event_dict)
            result = ExecutionResult(
                status="DISPATCHED",
                tool="escalation_api",
                action=action,
                dispatch_id=details["dispatch_id"],
                details=details,
                timestamp=now_iso
            )
        else:
            # Fallback for unrecognized action
            result = ExecutionResult(
                status="SUPPRESSED",
                tool="none",
                action=action,
                dispatch_id="none",
                details={"message": f"Unrecognized action '{action}' suppressed by default."},
                timestamp=now_iso
            )

        # Log ACTION_EXECUTED to SQLite Audit Log
        AuditLogger.log_event(
            session=session,
            case_id=case.id,
            event_type="ACTION_EXECUTED",
            detail_dict={
                "action": result.action,
                "status": result.status,
                "tool": result.tool,
                "dispatch_id": result.dispatch_id,
                "details": result.details
            }
        )

        return result
