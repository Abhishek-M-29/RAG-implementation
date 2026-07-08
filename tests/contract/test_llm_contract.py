"""
Gemini (LLM) test strategy: fully mocked.

GoogleGenAIProvider.from_config() constructs a ChatGoogleGenerativeAI object
without making network calls (the API key is stored but not validated until
_generate()). The invoke test patches the inner model's _generate() to return a
ChatResult directly, avoiding any real API call.

Rationale:
- Zero API cost — no Gemini API key needed in CI.
- Zero CI flakiness — no dependency on external service availability.
- Zero CI configuration — no secret injection required for test execution.

If a future adopter wants to run these tests against a real Gemini endpoint,
they can replace the mock with a live call by providing LLM_CONFIG__API_KEY
and removing the patch on model._inner._generate.
"""

from unittest.mock import patch

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from ragframework.llms.registry import LLM_PROVIDER_REGISTRY


def _config_for(name):
    if name == "google_genai":
        return {"api_key": "test-fake-key-for-contract-test"}
    msg = f"test_config_for has no config for {name!r}"
    raise ValueError(msg)


@pytest.mark.parametrize("name,cls", LLM_PROVIDER_REGISTRY.items())
def test_from_config_returns_chat_model(name, cls):
    config = _config_for(name)
    model = cls.from_config(config)
    assert isinstance(model, BaseChatModel)


@pytest.mark.parametrize("name,cls", LLM_PROVIDER_REGISTRY.items())
def test_from_config_invoke_succeeds(name, cls):
    config = _config_for(name)
    model = cls.from_config(config)

    with patch.object(model._inner, "_generate") as mock_generate:
        mock_generate.return_value = ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="pong"))]
        )
        result = model.invoke([HumanMessage(content="ping")])
        assert result.content is not None
        assert len(result.content) > 0
