"""mmt-plugin-agent: a LangGraph agent (deepagents) that runs the
mmt-plugin-generator skill headless, with any LLM provider (#161).

The public API is ``__all__`` (``docs/agent-api.md``). Running it needs the
``agent`` extra (Python 3.11+); importing this package does not, so the
console script can say what is missing.
"""

from __future__ import annotations

from mmt_plugin import __version__
from mmt_plugin_agent.api import PluginAgent, extra_missing
from mmt_plugin_agent.doctor import DoctorCheck, DoctorReport
from mmt_plugin_agent.errors import AgentError
from mmt_plugin_agent.evals import CaseOutcome, ModelEvalReport, run_model_evals
from mmt_plugin_agent.graph import build_graph, request_text
from mmt_plugin_agent.questions import Question
from mmt_plugin_agent.result import AgentEvent, AgentResult, LoopRun

__all__ = [
    "AgentError",
    "AgentEvent",
    "AgentResult",
    "CaseOutcome",
    "DoctorCheck",
    "DoctorReport",
    "LoopRun",
    "ModelEvalReport",
    "PluginAgent",
    "Question",
    "__version__",
    "build_graph",
    "extra_missing",
    "request_text",
    "run_model_evals",
]
