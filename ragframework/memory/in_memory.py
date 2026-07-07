import threading

from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory

from ragframework.memory.base import BaseSessionMemory


class InMemorySessionMemory(BaseSessionMemory):
    def __init__(self):
        self._stores: dict[str, InMemoryChatMessageHistory] = {}
        self._lock = threading.Lock()

    def get_history(self, session_id: str) -> BaseChatMessageHistory:
        with self._lock:
            if session_id not in self._stores:
                self._stores[session_id] = InMemoryChatMessageHistory()
            return self._stores[session_id]

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._stores.pop(session_id, None)

    def append(self, session_id: str, message: dict) -> None:
        history = self.get_history(session_id)
        role = message.get("role", "human")
        content = message.get("content", "")
        if role == "human":
            history.add_user_message(content)
        else:
            history.add_ai_message(content)
