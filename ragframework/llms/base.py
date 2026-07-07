from abc import ABC, abstractmethod

from langchain_core.language_models.chat_models import BaseChatModel


class BaseLLMProvider(ABC):
    """Contract every LLM connector must implement."""

    @classmethod
    @abstractmethod
    def from_config(cls, config: dict) -> BaseChatModel:
        """Return a ready-to-use LangChain chat model using the adopter's own API key."""
