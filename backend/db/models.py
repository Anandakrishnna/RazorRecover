from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field

class Merchant(SQLModel, table=True):
    __tablename__ = "merchants"
    
    id: str = Field(primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Customer(SQLModel, table=True):
    __tablename__ = "customers"
    
    id: str = Field(primary_key=True)
    merchant_id: str = Field(foreign_key="merchants.id")
    name: str
    subscription_status: str = Field(default="N/A") # ACTIVE, PAST_DUE, PAUSED, CANCELLED, N/A
    previous_recovery_outcome: Optional[str] = Field(default="NONE") # RECOVERED, FAILED, NONE
    history_json: Optional[str] = Field(default="{}") # JSON string of purchase history

class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    
    id: str = Field(primary_key=True)
    merchant_id: str = Field(foreign_key="merchants.id")
    customer_id: str = Field(foreign_key="customers.id")
    amount: float
    method: str # card, upi, netbanking, invoice
    status: str # SUCCESS, FAILED, PENDING
    failure_type: str # temporary, card_expired, insufficient_funds, checkout_abandoned, subscription_failed, overdue_invoice
    retry_count: int = Field(default=0)
    checkout_behavior: Optional[str] = Field(default="N/A")
    invoice_age_days: int = Field(default=0)
    retry_history_json: Optional[str] = Field(default="[]")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RecoveryCase(SQLModel, table=True):
    __tablename__ = "recovery_cases"
    
    id: str = Field(primary_key=True)
    transaction_id: str = Field(foreign_key="transactions.id")
    revenue_at_risk: float
    root_cause: str
    confidence: float
    recovery_probability: float
    expected_recovery_value: float
    status: str = Field(default="OPEN") # OPEN, IN_PROGRESS, RECOVERED, FAILED, ESCALATED, STOPPED
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = Field(default=None)

class AgentDecision(SQLModel, table=True):
    __tablename__ = "agent_decisions"
    
    id: str = Field(primary_key=True)
    case_id: str = Field(foreign_key="recovery_cases.id")
    recommendation: str
    policy_check_result: str # APPROVED, DOWNGRADED, REJECTED
    action_taken: str
    result: str # SUCCESS, FAILED, PENDING
    reasoning_text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    
    id: str = Field(primary_key=True)
    case_id: str = Field(foreign_key="recovery_cases.id")
    event_type: str # EVENT_INGESTED, CLASSIFIED, POLICY_CHECK, ACTION_EXECUTED, VERIFIED, ESCALATED
    detail_json: str # Stringified JSON payload
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
