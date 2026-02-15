"""Notification endpoints — list, mark read, preferences."""

import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.db.session import get_db
from app.models.user import User
from app.models.notification import Notification, NotificationPreference
from app.api.v1.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schemas ──

class NotificationResponse(BaseModel):
    id: str
    category: str
    title: str
    message: str
    is_read: bool
    data: dict | None = None
    link: str | None = None
    created_at: str


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int
    total: int


class PreferencesResponse(BaseModel):
    in_app_enabled: bool = True
    email_enabled: bool = False
    trade_alerts: bool = True
    agent_alerts: bool = True
    order_alerts: bool = True
    position_alerts: bool = True
    system_alerts: bool = True
    email_address: str | None = None


class PreferencesUpdate(BaseModel):
    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
    trade_alerts: bool | None = None
    agent_alerts: bool | None = None
    order_alerts: bool | None = None
    position_alerts: bool | None = None
    system_alerts: bool | None = None
    email_address: str | None = None


# ── Endpoints ──

@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    category: str | None = None,
    unread_only: bool = False,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List notifications for the current user."""
    query = select(Notification).where(Notification.user_id == user.id)
    if category:
        query = query.where(Notification.category == category)
    if unread_only:
        query = query.where(Notification.is_read == False)  # noqa: E712
    query = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    notifications = result.scalars().all()

    # Unread count
    count_query = select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id,
        Notification.is_read == False,  # noqa: E712
    )
    count_result = await db.execute(count_query)
    unread_count = count_result.scalar() or 0

    # Total count
    total_query = select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id,
    )
    total_result = await db.execute(total_query)
    total = total_result.scalar() or 0

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=str(n.id),
                category=n.category,
                title=n.title,
                message=n.message,
                is_read=n.is_read,
                data=n.data,
                link=n.link,
                created_at=n.created_at.isoformat() if n.created_at else "",
            )
            for n in notifications
        ],
        unread_count=unread_count,
        total=total,
    )


@router.get("/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get unread notification count (lightweight poll)."""
    result = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user.id,
            Notification.is_read == False,  # noqa: E712
        )
    )
    return {"unread_count": result.scalar() or 0}


@router.post("/{notification_id}/read", status_code=200)
async def mark_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a single notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == uuid.UUID(notification_id),
            Notification.user_id == user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    await db.commit()
    return {"status": "ok"}


@router.post("/read-all", status_code=200)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark all notifications as read."""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    await db.commit()
    return {"status": "ok"}


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get notification preferences."""
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        return PreferencesResponse()

    return PreferencesResponse(
        in_app_enabled=pref.in_app_enabled,
        email_enabled=pref.email_enabled,
        trade_alerts=pref.trade_alerts,
        agent_alerts=pref.agent_alerts,
        order_alerts=pref.order_alerts,
        position_alerts=pref.position_alerts,
        system_alerts=pref.system_alerts,
        email_address=pref.email_address,
    )


@router.put("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    req: PreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update notification preferences."""
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    pref = result.scalar_one_or_none()

    if not pref:
        pref = NotificationPreference(
            user_id=user.id,
            in_app_enabled=True,
            email_enabled=False,
            trade_alerts=True,
            agent_alerts=True,
            order_alerts=True,
            position_alerts=True,
            system_alerts=True,
        )
        db.add(pref)

    updates = req.model_dump(exclude_unset=True)
    for key, val in updates.items():
        setattr(pref, key, val)

    await db.flush()
    await db.commit()

    return PreferencesResponse(
        in_app_enabled=pref.in_app_enabled,
        email_enabled=pref.email_enabled,
        trade_alerts=pref.trade_alerts,
        agent_alerts=pref.agent_alerts,
        order_alerts=pref.order_alerts,
        position_alerts=pref.position_alerts,
        system_alerts=pref.system_alerts,
        email_address=pref.email_address,
    )
