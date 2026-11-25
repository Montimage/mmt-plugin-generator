"""``build_graph()`` is a compiled LangGraph graph that another
application uses as a subgraph (AC12)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from mmt_plugin_agent import build_graph, request_text

from .fakes import FakeCli, call, scripted, step

SPEC = Path(__file__).resolve().parents[3] / (
    "skills/mmt-plugin-generator/evals/cases/spec-telem/spec.md"
)


def test_the_graph_runs_as_a_node_of_another_graph(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    cli = fake_cli()
    work = tmp_path / "work"
    command = f"mmt-plugin -C {work}/project --json validate --no-sdk"
    model = scripted([step(call("execute", command=command)), "DONE from the subgraph"])
    parent = StateGraph(MessagesState)
    parent.add_node("plugin", build_graph(model, work_dir=work))
    parent.add_edge(START, "plugin")
    parent.add_edge("plugin", END)
    app = parent.compile()
    out = app.invoke(MessagesState(messages=[HumanMessage(content=request_text(spec=SPEC))]))
    assert out["messages"][-1].content == "DONE from the subgraph"
    assert cli.calls() == [["-C", f"{work}/project", "--json", "validate", "--no-sdk"]]
    assert "unattended: no user can answer" in str(model.seen[0][0].content)
