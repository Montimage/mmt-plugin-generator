"""The chat model: a LangChain chat model, or a ``provider:model`` string
that LangChain's ``init_chat_model`` resolves (no provider is built in)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from mmt_plugin.exitcodes import ExitCode
from mmt_plugin_agent.errors import AgentError

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

__all__ = ["DEFAULT_NUM_CTX", "ENV_MODEL", "ENV_NUM_CTX", "model_spec", "resolve_model"]

ENV_MODEL = "MMT_PLUGIN_AGENT_MODEL"
ENV_NUM_CTX = "MMT_PLUGIN_AGENT_NUM_CTX"
#: An Ollama model's context length (``num_ctx``). Ollama's own default
#: (2048 or 4096 tokens) is shorter than the agent's system prompt and
#: tools: Ollama then drops the start of the conversation, the user message
#: with it.
DEFAULT_NUM_CTX = 65536


def model_spec(model: str | None) -> str | None:
    """The model's ``provider:model`` string: ``model``, else
    ``MMT_PLUGIN_AGENT_MODEL``."""
    return model or os.environ.get(ENV_MODEL) or None


def _num_ctx() -> int:
    """``MMT_PLUGIN_AGENT_NUM_CTX``, else ``DEFAULT_NUM_CTX``."""
    raw = os.environ.get(ENV_NUM_CTX, "").strip()
    if not raw:
        return DEFAULT_NUM_CTX
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise AgentError(
            ExitCode.USAGE,
            "agent.bad-model",
            f"{ENV_NUM_CTX}={raw!r} is not a positive integer",
            f"set {ENV_NUM_CTX} to the Ollama context length in tokens, "
            f"or unset it for {DEFAULT_NUM_CTX}",
        )
    return value


def resolve_model(model: str | BaseChatModel | None) -> BaseChatModel:
    """A chat model from ``model``: a chat model as it is, else
    ``init_chat_model(provider:model)`` (``anthropic:...``, ``openai:...``
    with ``OPENAI_BASE_URL`` for vLLM, ``ollama:...`` with ``num_ctx`` from
    ``MMT_PLUGIN_AGENT_NUM_CTX``, 65536 by default)."""
    from langchain.chat_models import init_chat_model
    from langchain_core.language_models import BaseChatModel

    if isinstance(model, BaseChatModel):
        return model
    spec = model_spec(model)
    if spec is None:
        raise AgentError(
            ExitCode.USAGE,
            "agent.no-model",
            "no model configured",
            f"pass --model PROVIDER:MODEL (or set {ENV_MODEL}), e.g. anthropic:<model>, "
            "openai:<model> with OPENAI_BASE_URL for vLLM, ollama:<model>",
        )
    if ":" not in spec:
        raise AgentError(
            ExitCode.USAGE,
            "agent.bad-model",
            f"model {spec!r} names no provider",
            "write the model as PROVIDER:MODEL, e.g. anthropic:<model> or ollama:<model>",
        )
    kwargs: dict[str, Any] = {}
    if spec.split(":", 1)[0].strip().lower() == "ollama":
        kwargs["num_ctx"] = _num_ctx()
    try:
        chat: BaseChatModel = init_chat_model(spec, **kwargs)
        return chat
    except (ValueError, ImportError) as exc:
        raise AgentError(
            ExitCode.USAGE,
            "agent.bad-model",
            f"cannot use the model {spec!r}: {exc}",
            "use a provider the agent extra installs: anthropic, openai or ollama",
        ) from exc
