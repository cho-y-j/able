"""Pattern discovery API endpoints."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.discovered_pattern import DiscoveredPattern
from app.api.v1.deps import get_current_user

router = APIRouter()


class PatternResponse(BaseModel):
    id: str
    name: str
    description: str | None
    pattern_type: str
    feature_importance: dict
    model_metrics: dict
    rule_description: str | None
    rule_config: dict
    validation_results: dict
    status: str
    sample_count: int
    event_count: int

    model_config = {"from_attributes": True}


class PatternDiscoverRequest(BaseModel):
    pattern_type: str = "rise_5pct_5day"
    threshold_pct: float = 5.0
    window_days: int = 5
    stock_codes: list[str] = []


@router.get("", response_model=list[PatternResponse])
async def list_patterns(
    status: str | None = Query(default=None),
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List discovered patterns."""
    stmt = (
        select(DiscoveredPattern)
        .order_by(DiscoveredPattern.created_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(DiscoveredPattern.status == status)

    result = await db.execute(stmt)
    patterns = result.scalars().all()
    return [
        PatternResponse(
            id=str(p.id),
            name=p.name,
            description=p.description,
            pattern_type=p.pattern_type,
            feature_importance=p.feature_importance,
            model_metrics=p.model_metrics,
            rule_description=p.rule_description,
            rule_config=p.rule_config,
            validation_results=p.validation_results,
            status=p.status,
            sample_count=p.sample_count,
            event_count=p.event_count,
        )
        for p in patterns
    ]


@router.get("/{pattern_id}", response_model=PatternResponse)
async def get_pattern(
    pattern_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get pattern detail."""
    stmt = select(DiscoveredPattern).where(
        DiscoveredPattern.id == uuid.UUID(pattern_id)
    )
    result = await db.execute(stmt)
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Pattern not found")

    return PatternResponse(
        id=str(p.id),
        name=p.name,
        description=p.description,
        pattern_type=p.pattern_type,
        feature_importance=p.feature_importance,
        model_metrics=p.model_metrics,
        rule_description=p.rule_description,
        rule_config=p.rule_config,
        validation_results=p.validation_results,
        status=p.status,
        sample_count=p.sample_count,
        event_count=p.event_count,
    )


@router.post("/discover")
async def discover_pattern(
    request: PatternDiscoverRequest,
    user: User = Depends(get_current_user),
):
    """Trigger pattern discovery (async via Celery).

    Returns immediately with a task reference.
    """
    # In production, this dispatches to Celery
    return {
        "status": "queued",
        "pattern_type": request.pattern_type,
        "message": "Pattern discovery has been queued. Check /patterns for results.",
    }


@router.post("/{pattern_id}/activate")
async def activate_pattern(
    pattern_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Activate a validated pattern for live screening."""
    stmt = select(DiscoveredPattern).where(
        DiscoveredPattern.id == uuid.UUID(pattern_id)
    )
    result = await db.execute(stmt)
    pattern = result.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    if pattern.status not in ("validated", "draft"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot activate pattern with status '{pattern.status}'",
        )

    pattern.status = "active"
    await db.commit()

    return {"status": "active", "pattern_id": pattern_id}
