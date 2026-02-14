from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from app.integrations.llm.base import LLMProvider


class AnthropicProvider(LLMProvider):
    def create_chat_model(self, api_key: str, model_name: str = "claude-sonnet-4-5-20250929", **kwargs) -> BaseChatModel:
        return ChatAnthropic(
            api_key=api_key,
            model=model_name,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 4096),
        )

    async def validate_api_key(self, api_key: str) -> bool:
        try:
            model = ChatAnthropic(api_key=api_key, model="claude-haiku-4-5-20251001", max_tokens=5)
            await model.ainvoke("test")
            return True
        except Exception:
            return False

    def list_available_models(self) -> list[str]:
        return ["claude-opus-4-6", "claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001"]
