"""The chat model a ``provider:model`` string resolves to."""

from __future__ import annotations

from typing import Any

import pytest

from mmt_plugin_agent import models
from mmt_plugin_agent.errors import AgentError


def _kwargs(monkeypatch: pytest.MonkeyPatch, spec: str) -> dict[str, Any]:
    """What ``resolve_model(spec)`` passes to ``init_chat_model``."""
    import langchain.chat_models
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    seen: dict[str, Any] = {}

    def init(model: str, **kwargs: Any) -> FakeListChatModel:
        seen.update(kwargs, model=model)
        return FakeListChatModel(responses=["ok"])

    monkeypatch.setattr(langchain.chat_models, "init_chat_model", init)
    models.resolve_model(spec)
    return seen


def test_an_ollama_model_gets_a_context_length(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(models.ENV_NUM_CTX, raising=False)
    assert _kwargs(monkeypatch, "ollama:nimble:latest") == {
        "model": "ollama:nimble:latest",
        "num_ctx": models.DEFAULT_NUM_CTX,
    }
    monkeypatch.setenv(models.ENV_NUM_CTX, "131072")
    assert _kwargs(monkeypatch, "ollama:qwen3-coder")["num_ctx"] == 131072


def test_other_providers_get_no_context_length(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(models.ENV_NUM_CTX, "131072")
    assert _kwargs(monkeypatch, "openai:served") == {"model": "openai:served"}
    assert _kwargs(monkeypatch, "anthropic:claude-sonnet-5-5") == {
        "model": "anthropic:claude-sonnet-5-5"
    }


@pytest.mark.parametrize("value", ["0", "-1", "lots"])
def test_a_bad_context_length_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(models.ENV_NUM_CTX, value)
    with pytest.raises(AgentError) as raised:
        models.resolve_model("ollama:qwen3-coder")
    assert raised.value.code == "agent.bad-model"


def test_the_real_chat_ollama_has_the_context_length(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("langchain_ollama")
    monkeypatch.delenv(models.ENV_NUM_CTX, raising=False)
    model = models.resolve_model("ollama:nimble:latest")
    assert getattr(model, "num_ctx", None) == models.DEFAULT_NUM_CTX
