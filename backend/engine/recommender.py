import os
import json
import uuid
from typing import Dict, Any, Optional
from pydantic import BaseModel
from sqlmodel import Session
from backend.db.models import RecoveryCase, AgentDecision, AuditLog
from backend.engine.policy_engine import PolicyEngine

class LLMRecommendation(BaseModel):
    proposed_action: str
    reasoning_text: str
    source: str  # 'GEMINI_LIVE' or 'MOCK_FALLBACK'

class LLMRecommender:
    """
    AI Recommender component using LLM (Gemini) to propose recovery actions and reasoning.
    The LLM ONLY proposes actions; all proposals are strictly gated by the Policy Engine.
    Includes a robust offline mock fallback dictionary for API quota/network failure during demos.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def _mock_fallback_recommendation(self, event_dict: Dict[str, Any], root_cause: str) -> LLMRecommendation:
        """
        Deterministic mock fallback dictionary returning realistic AI recommendations & reasoning
        for pitch recordings, offline testing, or API rate-limit scenarios.
        """
        failure_type = event_dict.get("failure_type", "").lower()
        amount = float(event_dict.get("amount", 0.0))
        retry_count = int(event_dict.get("retry_count", 0))
        invoice_age = int(event_dict.get("invoice_age_days", 0))

        if failure_type == "card_expired":
            return LLMRecommendation(
                proposed_action="request_payment_method_update",
                reasoning_text="Expired card detected. Recommending dispatch of automated SMS/Email payment update link to customer.",
                source="MOCK_FALLBACK"
            )

        elif failure_type in ["temporary", "network_timeout", "bank_downtime"]:
            if amount >= 50000.0:
                return LLMRecommendation(
                    proposed_action="human_escalation",
                    reasoning_text=f"High transaction value (INR {amount:,.2f}) with network timeout. Recommending manual account manager outreach.",
                    source="MOCK_FALLBACK"
                )
            elif retry_count >= 2:
                return LLMRecommendation(
                    proposed_action="retry",  # Will be overridden to STOP by Policy Engine Rule 1
                    reasoning_text="Recommending additional payment retry to recover transient decline.",
                    source="MOCK_FALLBACK"
                )
            else:
                return LLMRecommendation(
                    proposed_action="retry",
                    reasoning_text="Transient network issue detected. Recommending immediate automated payment retry.",
                    source="MOCK_FALLBACK"
                )

        elif failure_type == "checkout_abandoned":
            return LLMRecommendation(
                proposed_action="send_recovery_message",
                reasoning_text="Cart abandoned during checkout. Recommending personalized WhatsApp recovery message with one-click checkout link.",
                source="MOCK_FALLBACK"
            )

        elif failure_type == "subscription_failed":
            if retry_count >= 3:
                return LLMRecommendation(
                    proposed_action="pause_subscription_and_escalate",
                    reasoning_text=f"Recurring subscription failed after {retry_count} attempts. Recommending subscription pause and support ticket creation.",
                    source="MOCK_FALLBACK"
                )
            else:
                return LLMRecommendation(
                    proposed_action="notify_customer_and_retry",
                    reasoning_text="Subscription renewal failed. Recommending customer notification email + scheduled 24h retry.",
                    source="MOCK_FALLBACK"
                )

        elif failure_type == "overdue_invoice":
            if invoice_age > 30:
                return LLMRecommendation(
                    proposed_action="human_escalation",
                    reasoning_text=f"B2B invoice severely overdue by {invoice_age} days. Recommending finance team escalation.",
                    source="MOCK_FALLBACK"
                )
            else:
                return LLMRecommendation(
                    proposed_action="reminder",
                    reasoning_text=f"B2B invoice overdue by {invoice_age} days. Recommending firm payment reminder email.",
                    source="MOCK_FALLBACK"
                )

        else:
            return LLMRecommendation(
                proposed_action="log_and_suppress",
                reasoning_text="Uncertain failure pattern. Recommending log-only to prevent unnecessary customer friction.",
                source="MOCK_FALLBACK"
            )

    def recommend(self, event_dict: Dict[str, Any], root_cause: str, force_live: bool = False) -> LLMRecommendation:
        """
        Generates LLM action recommendation and reasoning text.
        Tries live Gemini API if key is available; otherwise uses offline mock fallback.
        If force_live is True, errors will be raised directly instead of falling back to mock.
        """
        if not self.api_key:
            if force_live:
                raise ValueError("GEMINI_API_KEY environment variable is not set!")
            return self._mock_fallback_recommendation(event_dict, root_cause)

        try:
            prompt = f"""
You are RazorRecover AI, an autonomous revenue recovery agent.
Analyze the following merchant revenue failure event and propose the best intervention.

Event Context:
- Transaction ID: {event_dict.get('transaction_id')}
- Failure Type: {event_dict.get('failure_type')}
- Amount: INR {event_dict.get('amount')}
- Root Cause Diagnosed: {root_cause}
- Retry Count: {event_dict.get('retry_count')}
- Invoice Age Days: {event_dict.get('invoice_age_days')}
- Customer Purchase History: {event_dict.get('customer_purchase_history')}

Available Actions:
[retry, scheduled_retry_24h, request_payment_method_update, send_recovery_message, notify_customer_and_retry, reminder, gentle_reminder, pause_subscription_and_escalate, human_escalation, log_and_suppress]

Respond ONLY in valid JSON format:
{{
  "proposed_action": "<action>",
  "reasoning_text": "<concise explanation of rationale>"
}}
"""
            # Try new google-genai SDK first
            try:
                from google import genai
                client = genai.Client(api_key=self.api_key)
                text = None
                for model_name in ["gemini-2.5-flash", "gemini-flash-latest", "gemini-3.6-flash"]:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config={"response_mime_type": "application/json"}
                        )
                        text = response.text
                        break
                    except Exception:
                        continue
                if text is None:
                    raise RuntimeError("No compatible Gemini model succeeded.")
            except Exception as inner_e:
                try:
                    import google.generativeai as genai_legacy
                    genai_legacy.configure(api_key=self.api_key)
                    model = genai_legacy.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(
                        prompt,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    text = response.text
                except Exception as legacy_e:
                    if force_live:
                        raise RuntimeError(f"Live Gemini API call failed: {inner_e} | Legacy fallback failed: {legacy_e}")
                    raise inner_e

            data = json.loads(text)
            return LLMRecommendation(
                proposed_action=data.get("proposed_action", "log_and_suppress"),
                reasoning_text=data.get("reasoning_text", "AI recommendation generated via Gemini."),
                source="GEMINI_LIVE"
            )
        except Exception as outer_e:
            if force_live:
                raise outer_e
            # On any API error, network timeout, or quota exhaustion, fallback gracefully
            return self._mock_fallback_recommendation(event_dict, root_cause)

    def recommend_and_gate_with_policy(
        self,
        case: RecoveryCase,
        event_dict: Dict[str, Any],
        policy_engine: PolicyEngine,
        session: Session,
        force_live: bool = False
    ) -> AgentDecision:
        """
        Runs LLM Recommender, then passes recommendation to PolicyEngine for gating.
        Persists decision to SQLite database.
        """
        rec = self.recommend(event_dict, case.root_cause, force_live=force_live)
        
        decision = policy_engine.process_and_update_case(
            case=case,
            event_dict=event_dict,
            proposed_action=rec.proposed_action,
            reasoning_text=f"[{rec.source}] {rec.reasoning_text}",
            session=session
        )
        return decision
