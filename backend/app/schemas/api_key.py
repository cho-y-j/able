from pydantic import BaseModel
from datetime import datetime


class KISCredentialRequest(BaseModel):
    app_key: str
    app_secret: str
    account_number: str
    is_paper_trading: bool = True
    label: str | None = None


class LLMCredentialRequest(BaseModel):
    provider_name: str  # 'openai', 'anthropic', 'google'
    api_key: str
    model_name: str  # 'gpt-4o', 'claude-sonnet-4-5-20250929', 'gemini-2.0-flash', etc.
    label: str | None = None


class ApiKeyResponse(BaseModel):
    id: str
    service_type: str
    provider_name: str
    label: str | None
    model_name: str | None
    is_active: bool
    is_paper_trading: bool
    last_validated_at: datetime | None
    masked_key: str  # e.g., "sk-...abc123"

    model_config = {"from_attributes": True}


class ApiKeyListResponse(BaseModel):
    keys: list[ApiKeyResponse]


class ValidateResponse(BaseModel):
    valid: bool
    message: str
