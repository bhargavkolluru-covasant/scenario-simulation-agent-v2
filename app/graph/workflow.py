import logging
from typing import Any, Awaitable, Callable

from langgraph.graph import StateGraph, END

from app.state.simulation_state import SimulationState

# Context
from app.nodes.context_node import context_node
from app.nodes.semantic_reasoning_node import semantic_reasoning_node

# Scenario and platform intelligence
from app.nodes.scenario_parser_node import scenario_parser_node
from app.nodes.dashboard_node import dashboard_node
from app.nodes.dashboard_context_resolver_node import dashboard_context_resolver_node
from app.nodes.scenario_intent_classifier_node import scenario_intent_classifier_node
from app.nodes.relevant_kpi_selector_node import relevant_kpi_selector_node
from app.nodes.entity_matching_node import entity_matching_node
from app.nodes.kpi_insights_node import kpi_insights_node
from app.nodes.risk_selector_node import risk_selector_node
from app.nodes.action_selector_node import action_selector_node
from app.nodes.financial_reasoning_selector_node import financial_reasoning_selector_node
from app.nodes.strategy_selector_node import strategy_selector_node
from app.nodes.actions_node import actions_node
from app.nodes.knowledge_graph_node import knowledge_graph_node
from app.nodes.rules_node import rules_node

# Simulation & Analysis
from app.nodes.simulation_node import simulation_node
from app.nodes.impact_analysis_node import impact_analysis_node
from app.nodes.recommendation_node import recommendation_node
from app.nodes.explainability_node import explainability_node
from app.nodes.report_generation_node import report_generation_node

logger = logging.getLogger(__name__)

REQUIRED_NODES = frozenset({
    "context",
    "scenario_parser",
    "dashboard_intelligence",
    "dashboard_context_resolver",
    "simulation",
})
OPTIONAL_NODE_FEATURES = {
    "recommendation": "recommendation_narrative",
    "explainability": "explainability",
    "report": "report_enrichment",
}
DEGRADED_STATUS = "COMPLETED_WITH_DEGRADED_FEATURES"


def route_required_node(state: SimulationState) -> str:
    return "stop" if state.get("status") == "FAILED" else "continue"


def _record_node_failure(state: SimulationState, node_name: str) -> None:
    state["failed_node"] = node_name
    if node_name in REQUIRED_NODES:
        state["status"] = "FAILED"
        return

    feature = OPTIONAL_NODE_FEATURES.get(node_name)
    if feature is None:
        state["status"] = "FAILED"
        return

    degraded_features = state.get("degraded_features")
    if not isinstance(degraded_features, list):
        degraded_features = []
    if feature not in degraded_features:
        degraded_features.append(feature)
    state["degraded_features"] = degraded_features
    state["status"] = DEGRADED_STATUS
    logger.warning(
        "[Workflow] Optional node failed; continuing with degraded feature=%s",
        feature,
    )


def classify_node(
    node_name: str,
    node: Callable[[SimulationState], Awaitable[SimulationState]],
) -> Callable[[SimulationState], Awaitable[SimulationState]]:
    async def run(state: SimulationState) -> SimulationState:
        state["current_node"] = node_name
        try:
            result = await node(state)
            if isinstance(result, dict):
                state = result
        except Exception:
            logger.exception("[Workflow] Node execution failed: %s", node_name)
            _record_node_failure(state, node_name)
            return state

        node_failed = state.get("status") == "FAILED"
        report = state.get("final_report")
        report_is_empty = (
            node_name == "report"
            and (
                not isinstance(report, dict)
                or not str(report.get("markdown_report") or "").strip()
            )
        )
        if node_failed or report_is_empty:
            _record_node_failure(state, node_name)
        elif state.get("degraded_features"):
            state["status"] = DEGRADED_STATUS
        return state

    run.__name__ = f"classified_{node_name}"
    return run


def _add_required_edge(node_name: str, next_node: str) -> None:
    graph.add_conditional_edges(
        node_name,
        route_required_node,
        {
            "continue": next_node,
            "stop": END,
        },
    )


# =====================================================
# LangGraph Initialization
# =====================================================

graph = StateGraph(SimulationState)

# =====================================================
# Register Nodes: 7 Decision Intelligence Nodes + Platform Services
# =====================================================

graph.add_node("context", classify_node("context", context_node))
graph.add_node("scenario_parser", classify_node("scenario_parser", scenario_parser_node))
graph.add_node(
    "dashboard_intelligence",
    classify_node("dashboard_intelligence", dashboard_node),
)

# Decision Intelligence Node 1: Dashboard Context Resolver
graph.add_node(
    "dashboard_context_resolver",
    classify_node("dashboard_context_resolver", dashboard_context_resolver_node),
)

# Decision Intelligence Node 2: Scenario Intent Classifier
graph.add_node("scenario_intent_classifier", scenario_intent_classifier_node)

# Decision Intelligence Node 3: Relevant KPI Selector
graph.add_node("relevant_kpi_selector", relevant_kpi_selector_node)

graph.add_node("entity_matching", entity_matching_node)
graph.add_node("kpi_insights", kpi_insights_node)

graph.add_node(
    "semantic_reasoning",
    semantic_reasoning_node
)

# Decision Intelligence Node 4: Risk Selector
graph.add_node("risk_selector", risk_selector_node)

# Decision Intelligence Node 5: Action Selector
graph.add_node("action_selector", action_selector_node)

# Decision Intelligence Node 7: Financial Reasoning Selector
graph.add_node("financial_reasoning_selector", financial_reasoning_selector_node)

# Decision Intelligence Node 6: Simulation Strategy Selector
graph.add_node("strategy_selector", strategy_selector_node)

graph.add_node("actions", actions_node)
graph.add_node("knowledge_graph", knowledge_graph_node)
graph.add_node("rules", rules_node)
graph.add_node("simulation", classify_node("simulation", simulation_node))
graph.add_node("impact_analysis", impact_analysis_node)
graph.add_node(
    "recommendation",
    classify_node("recommendation", recommendation_node),
)
graph.add_node(
    "explainability",
    classify_node("explainability", explainability_node),
)
graph.add_node("report", classify_node("report", report_generation_node))

# =====================================================
# Entry Point
# =====================================================

graph.set_entry_point("context")

# =====================================================
# Execution Flow
# =====================================================

_add_required_edge("context", "scenario_parser")
_add_required_edge("scenario_parser", "dashboard_intelligence")
_add_required_edge("dashboard_intelligence", "dashboard_context_resolver")
_add_required_edge("dashboard_context_resolver", "scenario_intent_classifier")
graph.add_edge("scenario_intent_classifier", "relevant_kpi_selector")
graph.add_edge("relevant_kpi_selector", "entity_matching")
graph.add_edge("entity_matching", "kpi_insights")
graph.add_edge("kpi_insights","semantic_reasoning")
graph.add_edge("semantic_reasoning","risk_selector")
graph.add_edge("risk_selector", "action_selector")
graph.add_edge("action_selector", "financial_reasoning_selector")
graph.add_edge("financial_reasoning_selector", "strategy_selector")
graph.add_edge("strategy_selector", "actions")
graph.add_edge("actions", "rules")
graph.add_edge("rules", "knowledge_graph")
graph.add_edge("knowledge_graph", "simulation")
_add_required_edge("simulation", "impact_analysis")
graph.add_edge("impact_analysis", "recommendation")
graph.add_edge("recommendation", "explainability")
graph.add_edge("explainability", "report")
graph.add_edge("report", END)

# =====================================================
# Compile Workflow
# =====================================================

workflow = graph.compile()

logger.info(
    "[Workflow] Scenario Simulation Agent graph compiled successfully."
)