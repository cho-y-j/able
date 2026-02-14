"""Service to build KIS client from user's encrypted credentials.

Caches KISClient instances per user to avoid repeated DB lookups,
credential decryption, and token re-issuance on every API call.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.api_credential import ApiCredential
from app.core.encryption import get_vault
from app.integrations.kis.client import KISClient

logger = logging.getLogger("able.kis.service")

# Global client cache: user_id → {"client", "created_at", "credential_id"}
_client_cache: dict[UUID, dict] = {}
_CACHE_TTL = timedelta(minutes=30)


async def get_kis_client(user_id, db: AsyncSession) -> KISClient:
    """Retrieve user's KIS credentials, decrypt, and build client.

    Returns a cached client if available and the credential hasn't changed.
    """
    uid = user_id if isinstance(user_id, UUID) else UUID(str(user_id))

    # Check cache
    cached = _client_cache.get(uid)
    if cached and (datetime.now(timezone.utc) - cached["created_at"]) < _CACHE_TTL:
        return cached["client"]

    result = await db.execute(
        select(ApiCredential).where(
            ApiCredential.user_id == uid,
            ApiCredential.service_type == "kis",
            ApiCredential.is_active == True,
        )
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise ValueError("No KIS API key configured. Please add your KIS credentials in Settings.")

    # If credential changed, invalidate cache
    if cached and cached.get("credential_id") != credential.id:
        logger.info("KIS credential changed for user %s, rebuilding client", uid)

    vault = get_vault()
    app_key = vault.decrypt(credential.encrypted_key)
    app_secret = vault.decrypt(credential.encrypted_secret)

    client = KISClient(
        app_key=app_key,
        app_secret=app_secret,
        account_number=credential.account_number,
        is_paper=credential.is_paper_trading,
    )

    _client_cache[uid] = {
        "client": client,
        "created_at": datetime.now(timezone.utc),
        "credential_id": credential.id,
    }
    logger.info("KIS client cached for user %s (paper=%s)", uid, credential.is_paper_trading)

    return client


def clear_client_cache(user_id=None):
    """Clear cached KIS clients. Pass user_id to clear a specific user."""
    if user_id:
        uid = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
        _client_cache.pop(uid, None)
    else:
        _client_cache.clear()
