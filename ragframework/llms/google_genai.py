from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from ragframework.llms.base import BaseLLMProvider
from ragframework.llms.retry import RetryableChatModel


class GoogleGenAIProvider(BaseLLMProvider):
    """Google Gemini LLM connector.

    Reads the model name and API key *only* from the adopter-supplied
    ``config`` dict.  No fallback to ``os.getenv`` – the adopter's
    configuration is the single source of truth.

    The returned model is wrapped in :class:`RetryableChatModel` which
    applies exponential-backoff retry on **transient** errors (rate
    limits, transient 5xx, connection resets). Authentication and
    validation errors are **not** retried.
    """

    @classmethod
    def from_config(cls, config: dict) -> BaseChatModel:
        api_key = config.get("api_key")
        model = config.get("model", "gemini-2.0-flash-lite")
        timeout = config.get("timeout")
        if not api_key:
            raise ValueError(
                "Gemini API key is required. "
                "Set LLM_CONFIG__API_KEY in your .env or provide api_key in llm_config."
            )
        kwargs = {"model": model, "google_api_key": api_key}
        if timeout is not None:
            kwargs["timeout"] = timeout
        raw = ChatGoogleGenerativeAI(**kwargs)
        return RetryableChatModel(raw)
