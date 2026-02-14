from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.api_credential import ApiCredential
from app.core.encryption import get_vault
from app.integrations.llm.openai_provider import OpenAIProvider
from app.integrations.llm.anthropic_provider import AnthropicProvider
from app.integrations.llm.google_provider import GoogleProvider
from app.integrations.llm.deepseek_provider import DeepSeekProvider

PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "deepseek": DeepSeekProvider,
}

SUPPORTED_MODELS = {}
for name, cls in PROVIDERS.items():
    p = cls()
    for model in p.list_available_models():
        SUPPORTED_MODELS[model] = name


async def get_llm_for_user(user_id, db: AsyncSession) -> BaseChatModel:
    """Retrieve user's LLM config, decrypt API key, instantiate model."""
    result = await db.execute(
        select(ApiCredential).where(
            ApiCredential.user_id == user_id,
            ApiCredential.service_type == "llm",
            ApiCredential.is_active == True,
        )
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise ValueError("No LLM API key configured. Please add your LLM API key in Settings.")

    vault = get_vault()
    decrypted_key = vault.decrypt(credential.encrypted_key)

    provider_class = PROVIDERS.get(credential.provider_name)
    if not provider_class:
        raise ValueError(f"Unsupported LLM provider: {credential.provider_name}")

    provider = provider_class()
    return provider.create_chat_model(
        api_key=decrypted_key,
        model_name=credential.model_name or provider.list_available_models()[0],
    )


def get_supported_providers() -> dict:
    """Return supported providers and their models for the frontend."""
    return {
        name: cls().list_available_models()
        for name, cls in PROVIDERS.items()
    }
