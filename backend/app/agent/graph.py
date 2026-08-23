from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    node_analyze,
    node_check_eligibility,
    node_decide,
    node_escalate,
    node_execute_action,
    node_monitor,
    node_stop,
    route_decision,
    route_eligibility,
    route_monitor,
)
from app.agent.state import RecoveryState
from app.services.actions.executor import ActionExecutor


def build_recovery_graph(executor: ActionExecutor) -> StateGraph:
    """
    Constructs the LangGraph recovery workflow.

    Graph structure:
        START → analyze → check_eligibility → decide →(route)→ execute_action → monitor →(route)→ stop/escalate
                                                      ↓
                                                 stop / escalate
    """
    graph = StateGraph(RecoveryState)

    graph.add_node("analyze", node_analyze)
    graph.add_node("check_eligibility", node_check_eligibility)
    graph.add_node("decide", node_decide)
    graph.add_node("execute_action", partial(node_execute_action, executor=executor))
    graph.add_node("monitor", node_monitor)
    graph.add_node("stop", node_stop)
    graph.add_node("escalate", node_escalate)

    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "check_eligibility")

    graph.add_conditional_edges(
        "check_eligibility",
        route_eligibility,
        {"decide": "decide"},
    )

    graph.add_conditional_edges(
        "decide",
        route_decision,
        {
            "execute_action": "execute_action",
            "escalate": "escalate",
            "stop": "stop",
        },
    )

    graph.add_edge("execute_action", "monitor")

    graph.add_conditional_edges(
        "monitor",
        route_monitor,
        {"stop": "stop", "escalate": "escalate"},
    )

    graph.add_edge("stop", END)
    graph.add_edge("escalate", END)

    return graph
