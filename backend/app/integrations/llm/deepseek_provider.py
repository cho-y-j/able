from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from app.integrations.llm.base import LLMProvider


class DeepSeekProvider(LLMProvider):
    BASE_URL = "https://api.deepseek.com"

    def create_chat_model(self, api_key: str, model_name: str = "deepseek-chat", **kwargs) -> BaseChatModel:
        return ChatOpenAI(
            api_key=api_key,
            model=model_name,
            base_url=self.BASE_URL,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 4096),
        )

    async def validate_api_key(self, api_key: str) -> bool:
        try:
            model = ChatOpenAI(
                api_key=api_key,
                model="deepseek-chat",
                base_url=self.BASE_URL,
                max_tokens=5,
            )
            await model.ainvoke("test")
            return True
        except Exception:
            return False

    def list_available_models(self) -> list[str]:
        return ["deepseek-chat", "deepseek-reasoner"]
