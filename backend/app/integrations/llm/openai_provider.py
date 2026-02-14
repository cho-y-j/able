from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from app.integrations.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):
    def create_chat_model(self, api_key: str, model_name: str = "gpt-4o", **kwargs) -> BaseChatModel:
        return ChatOpenAI(
            api_key=api_key,
            model=model_name,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 4096),
        )

    async def validate_api_key(self, api_key: str) -> bool:
        try:
            model = ChatOpenAI(api_key=api_key, model="gpt-4o-mini", max_tokens=5)
            await model.ainvoke("test")
            return True
        except Exception:
            return False

    def list_available_models(self) -> list[str]:
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o3-mini"]
