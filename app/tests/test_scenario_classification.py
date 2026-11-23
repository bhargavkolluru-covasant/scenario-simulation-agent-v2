import pytest

import app.nodes.semantic_reasoning_node as semantic_node_module
from app.nodes.scenario_intent_classifier_node import scenario_intent_classifier_node
from app.nodes.scenario_parser_node import scenario_parser_node
from app.nodes.strategy_selector_node import strategy_selector_node


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "scenario_type", "target_entity", "change_type", "expected_category"),
    [
        (
            "Revenue increases by 20%",
            "revenue_change",
            "Revenue",
            "increase",
            "REVENUE_GROWTH",
        ),
        (
            "Revenue decreases by 20%",
            "revenue_change",
            "Revenue",
            "decrease",
            "REVENUE_DECLINE",
        ),
        (
            "Cost increases by 15%",
            "cost_change",
            "Cost",
            "increase",
            "COST_INCREASE",
        ),
        (
            "Cost decreases by 15%",
            "cost_change",
            "Cost",
            "decrease",
            "COST_DECREASE",
        ),
    ],
)
async def test_workflow_classification_follows_parsed_change_direction(
    monkeypatch,
    query,
    scenario_type,
    target_entity,
    change_type,
    expected_category,
):
    class ParsedScenario:
        async def parse(self, query):
            del query
            return {
                "scenario_type": scenario_type,
                "target_entity": target_entity,
                "change_type": change_type,
                "change_percentage": 20 if target_entity == "Revenue" else 15,
                "time_horizon": "unspecified",
            }

    class SemanticReasoning:
        async def reason(self, **kwargs):
            del kwargs
            return {}

    monkeypatch.setattr(
        semantic_node_module,
        "SemanticReasoningService",
        SemanticReasoning,
    )
    state = {"query": query}

    await scenario_parser_node(state, service=ParsedScenario())
    await scenario_intent_classifier_node(state)

    scenario_context = state["scenario_context"]
    assert scenario_context["scenario_category"] == expected_category
    assert scenario_context["decision_type"] == expected_category
    assert scenario_context["scenario_semantics"]["intent_type"] == expected_category

    await semantic_node_module.semantic_reasoning_node(state)
    await strategy_selector_node(state)

    assert state["scenario_context"]["scenario_category"] == expected_category
    assert state["scenario_context"]["decision_type"] == expected_category
    assert (
        state["simulation_strategy_context"]["scenario_category"]
        == expected_category
    )
