from abc import ABC, abstractmethod

from langchain_core.chat_history import BaseChatMessageHistory


class BaseSessionMemory(ABC):
    @abstractmethod
    def get_history(self, session_id: str) -> BaseChatMessageHistory:
        ...

    @abstractmethod
    def append(self, session_id: str, message: dict) -> None:
        ...

    @abstractmethod
    def clear(self, session_id: str) -> None:
        ...
