from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel
from app.integrations.llm.base import LLMProvider


class GoogleProvider(LLMProvider):
    def create_chat_model(self, api_key: str, model_name: str = "gemini-2.0-flash", **kwargs) -> BaseChatModel:
        return ChatGoogleGenerativeAI(
            google_api_key=api_key,
            model=model_name,
            temperature=kwargs.get("temperature", 0.1),
            max_output_tokens=kwargs.get("max_tokens", 4096),
        )

    async def validate_api_key(self, api_key: str) -> bool:
        try:
            model = ChatGoogleGenerativeAI(
                google_api_key=api_key, model="gemini-2.0-flash", max_output_tokens=5,
            )
            await model.ainvoke("test")
            return True
        except Exception:
            return False

    def list_available_models(self) -> list[str]:
        return ["gemini-2.0-flash", "gemini-2.5-pro", "gemini-2.5-flash"]
