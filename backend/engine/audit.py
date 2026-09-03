import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlmodel import Session
from backend.db.models import AuditLog

class AuditLogger:
    """
    Centralized Audit Logger for RazorRecover agent loop.
    Logs structured event records into the SQLite audit_log table.
    """

    VALID_EVENT_TYPES = {
        "EVENT_INGESTED",
        "CLASSIFIED",
        "RECOVERY_PREDICTED",
        "POLICY_CHECK",
        "ACTION_EXECUTED",
        "VERIFIED",
        "ESCALATED",
        "STOPPED"
    }

    @classmethod
    def log_event(
        cls,
        session: Session,
        case_id: str,
        event_type: str,
        detail_dict: Dict[str, Any]
    ) -> AuditLog:
        """
        Creates and persists a structured AuditLog entry in the database.
        """
        audit_id = f"audit_{uuid.uuid4().hex[:8]}"
        detail_json_str = json.dumps(detail_dict, default=str)

        audit_entry = AuditLog(
            id=audit_id,
            case_id=case_id,
            event_type=event_type,
            detail_json=detail_json_str,
            timestamp=datetime.now(timezone.utc)
        )
        session.add(audit_entry)
        session.flush()
        return audit_entry
