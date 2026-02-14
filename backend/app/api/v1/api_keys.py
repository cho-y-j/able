from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.api_credential import ApiCredential
from app.schemas.api_key import (
    KISCredentialRequest, LLMCredentialRequest,
    ApiKeyResponse, ApiKeyListResponse, ValidateResponse,
)
from app.core.encryption import get_vault
from app.core.audit import audit_key_event, AuditAction
from app.api.v1.deps import get_current_user

router = APIRouter()


def mask_key(key: str) -> str:
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "..." + key[-4:]


@router.post("/kis", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED,
              summary="Store KIS API credentials",
              description="Store encrypted KIS (한국투자증권) app key/secret. Previous active credentials are deactivated.")
async def store_kis_credentials(
    req: KISCredentialRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    vault = get_vault()

    # Deactivate existing KIS credentials
    result = await db.execute(
        select(ApiCredential).where(
            ApiCredential.user_id == user.id,
            ApiCredential.service_type == "kis",
            ApiCredential.is_active == True,
        )
    )
    for old in result.scalars().all():
        old.is_active = False

    credential = ApiCredential(
        user_id=user.id,
        service_type="kis",
        provider_name="kis",
        label=req.label or "한국투자증권",
        encrypted_key=vault.encrypt(req.app_key),
        encrypted_secret=vault.encrypt(req.app_secret),
        account_number=req.account_number,
        is_active=True,
        is_paper_trading=req.is_paper_trading,
        last_validated_at=datetime.now(timezone.utc),
    )
    db.add(credential)
    await db.flush()

    audit_key_event(AuditAction.KEY_CREATED, str(user.id), str(credential.id), "kis")

    return ApiKeyResponse(
        id=str(credential.id),
        service_type=credential.service_type,
        provider_name=credential.provider_name,
        label=credential.label,
        model_name=None,
        is_active=True,
        is_paper_trading=credential.is_paper_trading,
        last_validated_at=credential.last_validated_at,
        masked_key=mask_key(req.app_key),
    )


@router.post("/llm", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED,
              summary="Store LLM API credentials",
              description="Store encrypted API key for OpenAI, Anthropic, or Google LLM providers.")
async def store_llm_credentials(
    req: LLMCredentialRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if req.provider_name not in ("openai", "anthropic", "google", "deepseek"):
        raise HTTPException(status_code=400, detail="Unsupported LLM provider")

    vault = get_vault()

    # Deactivate existing LLM credentials
    result = await db.execute(
        select(ApiCredential).where(
            ApiCredential.user_id == user.id,
            ApiCredential.service_type == "llm",
            ApiCredential.is_active == True,
        )
    )
    for old in result.scalars().all():
        old.is_active = False

    credential = ApiCredential(
        user_id=user.id,
        service_type="llm",
        provider_name=req.provider_name,
        label=req.label or f"{req.provider_name} - {req.model_name}",
        encrypted_key=vault.encrypt(req.api_key),
        model_name=req.model_name,
        is_active=True,
        last_validated_at=datetime.now(timezone.utc),
    )
    db.add(credential)
    await db.flush()

    audit_key_event(AuditAction.KEY_CREATED, str(user.id), str(credential.id), f"llm:{req.provider_name}")

    return ApiKeyResponse(
        id=str(credential.id),
        service_type=credential.service_type,
        provider_name=credential.provider_name,
        label=credential.label,
        model_name=credential.model_name,
        is_active=True,
        is_paper_trading=False,
        last_validated_at=credential.last_validated_at,
        masked_key=mask_key(req.api_key),
    )


@router.get("", response_model=ApiKeyListResponse, summary="List all stored API keys")
async def list_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ApiCredential).where(ApiCredential.user_id == user.id).order_by(ApiCredential.created_at.desc())
    )
    credentials = result.scalars().all()

    vault = get_vault()
    keys = []
    for cred in credentials:
        try:
            raw_key = vault.decrypt(cred.encrypted_key)
            masked = mask_key(raw_key)
        except Exception:
            masked = "***"

        keys.append(ApiKeyResponse(
            id=str(cred.id),
            service_type=cred.service_type,
            provider_name=cred.provider_name,
            label=cred.label,
            model_name=cred.model_name,
            is_active=cred.is_active,
            is_paper_trading=cred.is_paper_trading,
            last_validated_at=cred.last_validated_at,
            masked_key=masked,
        ))
    return ApiKeyListResponse(keys=keys)


@router.post("/{key_id}/validate", response_model=ValidateResponse,
              summary="Validate API credentials",
              description="Test that stored credentials actually work by making a test API call.")
async def validate_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Validate that stored API credentials actually work."""
    import uuid as _uuid
    result = await db.execute(
        select(ApiCredential).where(
            ApiCredential.id == _uuid.UUID(key_id),
            ApiCredential.user_id == user.id,
        )
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise HTTPException(status_code=404, detail="API key not found")

    vault = get_vault()

    if credential.service_type == "kis":
        try:
            from app.integrations.kis.client import KISClient
            app_key = vault.decrypt(credential.encrypted_key)
            app_secret = vault.decrypt(credential.encrypted_secret)
            client = KISClient(
                app_key=app_key,
                app_secret=app_secret,
                account_number=credential.account_number or "",
                is_paper=credential.is_paper_trading,
            )
            valid = await client.validate_credentials()
            if valid:
                credential.last_validated_at = datetime.now(timezone.utc)
            return ValidateResponse(
                valid=valid,
                message="KIS credentials are valid" if valid else "KIS credentials are invalid",
            )
        except Exception as e:
            return ValidateResponse(valid=False, message=f"Validation failed: {str(e)}")

    elif credential.service_type == "llm":
        try:
            api_key = vault.decrypt(credential.encrypted_key)
            provider = credential.provider_name

            if provider == "openai":
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=10.0,
                    )
                    valid = resp.status_code == 200
            elif provider == "anthropic":
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": credential.model_name or "claude-sonnet-4-5-20250929",
                            "max_tokens": 1,
                            "messages": [{"role": "user", "content": "hi"}],
                        },
                        timeout=10.0,
                    )
                    valid = resp.status_code == 200
            elif provider == "google":
                import httpx
                async with httpx.AsyncClient() as client:
                    model = credential.model_name or "gemini-2.0-flash"
                    resp = await client.get(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{model}",
                        params={"key": api_key},
                        timeout=10.0,
                    )
                    valid = resp.status_code == 200
            elif provider == "deepseek":
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        "https://api.deepseek.com/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": credential.model_name or "deepseek-chat",
                            "max_tokens": 1,
                            "messages": [{"role": "user", "content": "hi"}],
                        },
                        timeout=15.0,
                    )
                    valid = resp.status_code == 200
            else:
                return ValidateResponse(valid=False, message=f"Unknown provider: {provider}")

            if valid:
                credential.last_validated_at = datetime.now(timezone.utc)
            return ValidateResponse(
                valid=valid,
                message=f"{provider} API key is valid" if valid else f"{provider} API key is invalid",
            )
        except Exception as e:
            return ValidateResponse(valid=False, message=f"Validation failed: {str(e)}")

    return ValidateResponse(valid=False, message=f"Unknown service type: {credential.service_type}")


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an API key")
async def delete_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import uuid
    result = await db.execute(
        select(ApiCredential).where(
            ApiCredential.id == uuid.UUID(key_id),
            ApiCredential.user_id == user.id,
        )
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise HTTPException(status_code=404, detail="API key not found")
    audit_key_event(AuditAction.KEY_DELETED, str(user.id), key_id, credential.service_type)
    await db.delete(credential)


@router.post("/{key_id}/rotate", response_model=ApiKeyResponse,
              summary="Rotate encryption on a stored key",
              description="Re-encrypt credentials with current encryption key. Use after rotating ENCRYPTION_KEY.")
async def rotate_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Re-encrypt a stored credential with the current encryption key.

    Useful after rotating the ENCRYPTION_KEY: add the new key as primary
    and the old key as secondary in MultiFernet, then call this endpoint
    to re-encrypt all credentials under the new key.
    """
    import uuid as _uuid
    result = await db.execute(
        select(ApiCredential).where(
            ApiCredential.id == _uuid.UUID(key_id),
            ApiCredential.user_id == user.id,
        )
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise HTTPException(status_code=404, detail="API key not found")

    vault = get_vault()
    try:
        credential.encrypted_key = vault.rotate(credential.encrypted_key)
        if credential.encrypted_secret:
            credential.encrypted_secret = vault.rotate(credential.encrypted_secret)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rotation failed: {str(e)}")

    audit_key_event(AuditAction.KEY_ROTATED, str(user.id), key_id, credential.service_type)

    try:
        raw_key = vault.decrypt(credential.encrypted_key)
        masked = mask_key(raw_key)
    except Exception:
        masked = "***"

    return ApiKeyResponse(
        id=str(credential.id),
        service_type=credential.service_type,
        provider_name=credential.provider_name,
        label=credential.label,
        model_name=credential.model_name,
        is_active=credential.is_active,
        is_paper_trading=credential.is_paper_trading,
        last_validated_at=credential.last_validated_at,
        masked_key=masked,
    )
