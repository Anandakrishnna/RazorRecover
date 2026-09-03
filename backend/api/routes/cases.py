import json
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select, func
from backend.db.session import get_session
from backend.db.models import Merchant, Customer, Transaction, RecoveryCase, AgentDecision, AuditLog

router = APIRouter(prefix="/cases", tags=["Recovery Cases"])

@router.get("", status_code=status.HTTP_200_OK)
def list_cases(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by case status (OPEN, IN_PROGRESS, RECOVERED, FAILED, ESCALATED, STOPPED)"),
    merchant_id: Optional[str] = Query(None, description="Filter by merchant ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """
    Lists recovery cases sorted by expected_recovery_value DESC.
    Includes count total and paginated case objects.
    """
    statement = select(RecoveryCase, Transaction).join(Transaction, RecoveryCase.transaction_id == Transaction.id)

    if status_filter:
        statement = statement.where(RecoveryCase.status == status_filter.upper())
    if merchant_id:
        statement = statement.where(Transaction.merchant_id == merchant_id)

    # Calculate total count
    count_statement = select(func.count(RecoveryCase.id)).join(Transaction, RecoveryCase.transaction_id == Transaction.id)
    if status_filter:
        count_statement = count_statement.where(RecoveryCase.status == status_filter.upper())
    if merchant_id:
        count_statement = count_statement.where(Transaction.merchant_id == merchant_id)
    
    total_count = session.exec(count_statement).one()

    # Query paginated sorted cases
    statement = statement.order_by(RecoveryCase.expected_recovery_value.desc()).offset(offset).limit(limit)
    results = session.exec(statement).all()

    cases_list = []
    for case, tx in results:
        cases_list.append({
            "id": case.id,
            "transaction_id": case.transaction_id,
            "merchant_id": tx.merchant_id,
            "customer_id": tx.customer_id,
            "revenue_at_risk": case.revenue_at_risk,
            "root_cause": case.root_cause,
            "confidence": case.confidence,
            "recovery_probability": case.recovery_probability,
            "expected_recovery_value": case.expected_recovery_value,
            "status": case.status,
            "failure_type": tx.failure_type,
            "payment_method": tx.method,
            "opened_at": case.opened_at.isoformat() if case.opened_at else None,
            "closed_at": case.closed_at.isoformat() if case.closed_at else None
        })

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "cases": cases_list
    }

@router.get("/{case_id}", status_code=status.HTTP_200_OK)
def get_case_detail(
    case_id: str,
    session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """
    Returns full case detail including associated transaction, customer history, decisions, policy checks, and audit timeline.
    """
    case = session.get(RecoveryCase, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RecoveryCase with ID '{case_id}' not found."
        )

    transaction = session.get(Transaction, case.transaction_id)
    customer = session.get(Customer, transaction.customer_id) if transaction else None
    merchant = session.get(Merchant, transaction.merchant_id) if transaction else None

    # Retrieve decisions
    dec_stmt = select(AgentDecision).where(AgentDecision.case_id == case.id).order_by(AgentDecision.timestamp)
    decisions = session.exec(dec_stmt).all()

    # Retrieve audit log
    audit_stmt = select(AuditLog).where(AuditLog.case_id == case.id).order_by(AuditLog.timestamp)
    audit_logs = session.exec(audit_stmt).all()

    formatted_audit = []
    for log in audit_logs:
        try:
            detail_obj = json.loads(log.detail_json)
        except Exception:
            detail_obj = log.detail_json

        formatted_audit.append({
            "id": log.id,
            "event_type": log.event_type,
            "detail": detail_obj,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None
        })

    return {
        "case": {
            "id": case.id,
            "transaction_id": case.transaction_id,
            "revenue_at_risk": case.revenue_at_risk,
            "root_cause": case.root_cause,
            "confidence": case.confidence,
            "recovery_probability": case.recovery_probability,
            "expected_recovery_value": case.expected_recovery_value,
            "status": case.status,
            "opened_at": case.opened_at.isoformat() if case.opened_at else None,
            "closed_at": case.closed_at.isoformat() if case.closed_at else None
        },
        "merchant": {
            "id": merchant.id,
            "name": merchant.name
        } if merchant else None,
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "subscription_status": customer.subscription_status,
            "previous_recovery_outcome": customer.previous_recovery_outcome,
            "history": customer.history_json
        } if customer else None,
        "transaction": {
            "id": transaction.id,
            "amount": transaction.amount,
            "method": transaction.method,
            "failure_type": transaction.failure_type,
            "retry_count": transaction.retry_count,
            "checkout_behavior": transaction.checkout_behavior,
            "invoice_age_days": transaction.invoice_age_days,
            "retry_history": transaction.retry_history_json
        } if transaction else None,
        "decisions": [
            {
                "id": d.id,
                "recommendation": d.recommendation,
                "policy_check_result": d.policy_check_result,
                "action_taken": d.action_taken,
                "result": d.result,
                "reasoning_text": d.reasoning_text,
                "timestamp": d.timestamp.isoformat() if d.timestamp else None
            }
            for d in decisions
        ],
        "audit_log": formatted_audit
    }
