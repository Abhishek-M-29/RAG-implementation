from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from ragframework.memory.base import BaseSessionMemory


class _RedisChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, redis_client: redis.Redis, key: str):
        self._client = redis_client
        self._key = key

    def _load(self) -> list[BaseMessage]:
        raw_list = self._client.lrange(self._key, 0, -1)
        messages = []
        for item in raw_list:
            data = json.loads(item)
            role = data.get("role", "human")
            content = data.get("content", "")
            if role == "human":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))
        return messages

    @property
    def messages(self) -> list[BaseMessage]:
        return self._load()

    def add_message(self, message: BaseMessage) -> None:
        role = "human" if isinstance(message, HumanMessage) else "ai"
        self._client.rpush(
            self._key,
            json.dumps({"role": role, "content": message.content}, default=str),
        )

    def clear(self) -> None:
        self._client.delete(self._key)


class RedisSessionMemory(BaseSessionMemory):
    def __init__(self, redis_url: str):
        import redis

        self._client = redis.from_url(redis_url)

    def _history_key(self, session_id: str) -> str:
        return f"session:{session_id}:history"

    def get_history(self, session_id: str) -> BaseChatMessageHistory:
        return _RedisChatMessageHistory(self._client, self._history_key(session_id))

    def append(self, session_id: str, message: dict) -> None:
        self._client.rpush(
            self._history_key(session_id),
            json.dumps(message, default=str),
        )

    def clear(self, session_id: str) -> None:
        self._client.delete(self._history_key(session_id))
