"""Audit logger for security-sensitive events.

Logs authentication events, credential operations, and admin actions
to a dedicated 'audit' logger for compliance and forensics.
"""

import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

# Dedicated audit logger — configure separate handler in production
audit_logger = logging.getLogger("audit")


class AuditAction(str, Enum):
    # Auth events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    REGISTER = "register"
    TOKEN_REFRESH = "token_refresh"
    LOGOUT = "logout"

    # Account events
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    PASSWORD_CHANGED = "password_changed"

    # API key events
    KEY_CREATED = "key_created"
    KEY_DELETED = "key_deleted"
    KEY_VALIDATED = "key_validated"
    KEY_ROTATED = "key_rotated"

    # Trading events
    ORDER_PLACED = "order_placed"
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"


@dataclass
class AuditEntry:
    action: AuditAction
    user_id: str | None = None
    email: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    details: dict | None = None
    timestamp: str | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


def log_audit(entry: AuditEntry) -> None:
    """Write an audit log entry."""
    record = {
        "type": "audit",
        "action": entry.action.value,
        "ts": entry.timestamp,
        "user_id": entry.user_id,
        "email": entry.email,
        "ip": entry.ip_address,
        "ua": entry.user_agent,
    }
    if entry.details:
        record["details"] = entry.details

    audit_logger.info(
        f"AUDIT {entry.action.value} user={entry.user_id or 'anon'} "
        f"ip={entry.ip_address or 'unknown'}",
        extra={"audit_data": record},
    )


def audit_login_success(user_id: str, email: str, ip: str, ua: str) -> None:
    log_audit(AuditEntry(
        action=AuditAction.LOGIN_SUCCESS,
        user_id=user_id, email=email,
        ip_address=ip, user_agent=ua,
    ))


def audit_login_failed(email: str, ip: str, ua: str, reason: str = "invalid_credentials") -> None:
    log_audit(AuditEntry(
        action=AuditAction.LOGIN_FAILED,
        email=email, ip_address=ip, user_agent=ua,
        details={"reason": reason},
    ))


def audit_register(user_id: str, email: str, ip: str) -> None:
    log_audit(AuditEntry(
        action=AuditAction.REGISTER,
        user_id=user_id, email=email, ip_address=ip,
    ))


def audit_key_event(action: AuditAction, user_id: str, key_id: str, service_type: str) -> None:
    log_audit(AuditEntry(
        action=action,
        user_id=user_id,
        details={"key_id": key_id, "service_type": service_type},
    ))


def audit_account_locked(user_id: str, email: str, ip: str) -> None:
    log_audit(AuditEntry(
        action=AuditAction.ACCOUNT_LOCKED,
        user_id=user_id, email=email, ip_address=ip,
        details={"reason": "too_many_failed_attempts"},
    ))
