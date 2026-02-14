"""Service to build KIS client from user's encrypted credentials."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.api_credential import ApiCredential
from app.core.encryption import get_vault
from app.integrations.kis.client import KISClient


async def get_kis_client(user_id, db: AsyncSession) -> KISClient:
    """Retrieve user's KIS credentials, decrypt, and build client."""
    result = await db.execute(
        select(ApiCredential).where(
            ApiCredential.user_id == user_id,
            ApiCredential.service_type == "kis",
            ApiCredential.is_active == True,
        )
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise ValueError("No KIS API key configured. Please add your KIS credentials in Settings.")

    vault = get_vault()
    app_key = vault.decrypt(credential.encrypted_key)
    app_secret = vault.decrypt(credential.encrypted_secret)

    return KISClient(
        app_key=app_key,
        app_secret=app_secret,
        account_number=credential.account_number,
        is_paper=credential.is_paper_trading,
    )
