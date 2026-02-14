from abc import ABC, abstractmethod
from langchain_core.language_models import BaseChatModel


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def create_chat_model(self, api_key: str, model_name: str, **kwargs) -> BaseChatModel:
        ...

    @abstractmethod
    async def validate_api_key(self, api_key: str) -> bool:
        ...

    @abstractmethod
    def list_available_models(self) -> list[str]:
        ...
