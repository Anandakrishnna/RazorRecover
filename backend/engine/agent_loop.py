from typing import Dict, Any, Optional
from sqlmodel import Session, select
from backend.db.session import engine
from backend.db.models import RecoveryCase, AgentDecision, AuditLog
from backend.engine.revenue_monitor import RevenueMonitor
from backend.engine.classifier import RootCauseClassifier
from backend.engine.recovery_model import RecoveryProbabilityModel
from backend.engine.policy_engine import PolicyEngine
from backend.engine.recommender import LLMRecommender
from backend.engine.executor import ToolExecutor, ExecutionResult
from backend.engine.verifier import VerifierEngine, VerificationResult

def run_agent_pipeline(
    event_dict: Dict[str, Any],
    session: Optional[Session] = None,
    seed: Optional[int] = None,
    forced_roll: Optional[float] = None,
    api_key: Optional[str] = None,
    force_live: bool = False
) -> Dict[str, Any]:
    """
    Executes the full autonomous RazorRecover agent loop end-to-end:
    revenue_monitor → classifier → recovery_model → policy_engine → recommender → executor → verifier → audit
    
    Returns a comprehensive trace dictionary including all stage outputs and audit log entries.
    """
    db = session
    should_close = False
    if db is None:
        db = Session(engine)
        should_close = True

    try:
        # Step 1: Revenue Monitor Ingestion & Case Creation
        monitor = RevenueMonitor(session=db)
        is_at_risk, case = monitor.process_event(event_dict, session=db)

        if not is_at_risk or not case:
            return {
                "at_risk": False,
                "message": "Event is not flagged as revenue-at-risk. Agent pipeline bypassed.",
                "event": event_dict
            }

        # Step 2: Root Cause Classifier
        classifier = RootCauseClassifier()
        class_res = classifier.classify_and_update_case(case, event_dict, session=db)

        # Step 3: Recovery Probability Model
        model = RecoveryProbabilityModel()
        prob_res = model.predict_and_update_case(case, event_dict, session=db)

        # Step 4: AI Recommender & Policy Engine Gating
        policy_engine = PolicyEngine()
        recommender = LLMRecommender(api_key=api_key)
        decision = recommender.recommend_and_gate_with_policy(case, event_dict, policy_engine, session=db, force_live=force_live)

        # Step 5: Tool Executor (Simulated Action Dispatch)
        executor = ToolExecutor()
        exec_res = executor.execute_action(case, decision, event_dict, session=db)

        # Step 6: Verifier Engine (Probabilistic Outcome Roll)
        verifier = VerifierEngine()
        verif_res = verifier.verify_outcome(
            case=case,
            decision=decision,
            event_dict=event_dict,
            session=db,
            seed=seed,
            forced_roll=forced_roll
        )

        # Step 7: Audit Log Trace Retrieval
        statement = select(AuditLog).where(AuditLog.case_id == case.id).order_by(AuditLog.timestamp)
        audit_records = db.exec(statement).all()
        audit_trail = [
            {
                "id": record.id,
                "event_type": record.event_type,
                "detail": record.detail_json,
                "timestamp": record.timestamp.isoformat() if record.timestamp else None
            }
            for record in audit_records
        ]

        db.commit()
        db.refresh(case)

        return {
            "at_risk": True,
            "case_id": case.id,
            "transaction_id": event_dict.get("transaction_id"),
            "customer_id": event_dict.get("customer_id"),
            "amount": case.revenue_at_risk,
            "root_cause_diagnosis": {
                "root_cause": class_res.root_cause,
                "confidence": class_res.confidence,
                "reasoning": class_res.reasoning
            },
            "recovery_prediction": {
                "recovery_probability": prob_res.recovery_probability,
                "expected_recovery_value": prob_res.expected_recovery_value,
                "risk_tier": prob_res.risk_tier,
                "explanation": prob_res.explanation
            },
            "agent_decision": {
                "decision_id": decision.id,
                "proposed_recommendation": decision.recommendation,
                "policy_check_result": decision.policy_check_result,
                "allowed_action_taken": decision.action_taken,
                "reasoning_text": decision.reasoning_text
            },
            "execution_dispatch": exec_res.model_dump(),
            "verification_result": verif_res.model_dump(),
            "final_case_status": case.status,
            "closed_at": case.closed_at.isoformat() if case.closed_at else None,
            "audit_trail": audit_trail
        }

    finally:
        if should_close:
            db.close()
