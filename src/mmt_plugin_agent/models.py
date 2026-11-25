"""The chat model: a LangChain chat model, or a ``provider:model`` string
that LangChain's ``init_chat_model`` resolves (no provider is built in)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from mmt_plugin.exitcodes import ExitCode
from mmt_plugin_agent.errors import AgentError

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

__all__ = ["ENV_MODEL", "model_spec", "resolve_model"]

ENV_MODEL = "MMT_PLUGIN_AGENT_MODEL"


def model_spec(model: str | None) -> str | None:
    """The model's ``provider:model`` string: ``model``, else
    ``MMT_PLUGIN_AGENT_MODEL``."""
    return model or os.environ.get(ENV_MODEL) or None


def resolve_model(model: str | BaseChatModel | None) -> BaseChatModel:
    """A chat model from ``model``: a chat model as it is, else
    ``init_chat_model(provider:model)`` (``anthropic:...``, ``openai:...``
    with ``OPENAI_BASE_URL`` for vLLM, ``ollama:...``)."""
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
    try:
        return init_chat_model(spec)
    except (ValueError, ImportError) as exc:
        raise AgentError(
            ExitCode.USAGE,
            "agent.bad-model",
            f"cannot use the model {spec!r}: {exc}",
            "use a provider the agent extra installs: anthropic, openai or ollama",
        ) from exc
