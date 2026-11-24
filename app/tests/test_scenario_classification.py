import pytest

import app.nodes.semantic_reasoning_node as semantic_node_module
from app.nodes.scenario_intent_classifier_node import scenario_intent_classifier_node
from app.nodes.scenario_parser_node import scenario_parser_node
from app.nodes.strategy_selector_node import strategy_selector_node


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "scenario_type", "target_entity", "change_type"),
    [
        (
            "Revenue increases by 20%",
            "revenue_change",
            "Revenue",
            "increase",
        ),
        (
            "Revenue decreases by 20%",
            "revenue_change",
            "Revenue",
            "decrease",
        ),
        (
            "Cost increases by 15%",
            "cost_change",
            "Cost",
            "increase",
        ),
        (
            "Cost decreases by 15%",
            "cost_change",
            "Cost",
            "decrease",
        ),
    ],
)
async def test_unmapped_parsed_scenarios_remain_unclassified(
    monkeypatch,
    query,
    scenario_type,
    target_entity,
    change_type,
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
    assert scenario_context["scenario_type"] == scenario_type
    assert scenario_context["change_type"] == change_type
    assert scenario_context["scenario_category"] == "UNCLASSIFIED"
    assert scenario_context["decision_type"] == "UNCLASSIFIED"
    assert state["scenario_semantics"]["intent_type"] == "UNCLASSIFIED"
    assert state["scenario_semantics"]["themes"] == []
    assert "scenario_semantics" not in scenario_context

    await semantic_node_module.semantic_reasoning_node(state)
    await strategy_selector_node(state)

    assert state["scenario_context"]["scenario_category"] == "UNCLASSIFIED"
    assert state["scenario_context"]["decision_type"] == "UNCLASSIFIED"
    assert state["simulation_strategy_context"]["scenario_category"] == "UNCLASSIFIED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "dashboard_category",
        "scenario_type",
        "scenario_category",
        "strategy",
        "theme",
    ),
    [
        ("RETAIL", "population_growth", "DEMAND_GROWTH", "DEMAND_GROWTH", "demand"),
        ("LOGISTICS", "shipment_increase", "CAPACITY_PLANNING", "CAPACITY_PLANNING", "capacity"),
        ("FINANCE", "cash_flow_change", "FINANCIAL_CHANGE", "FINANCIAL_IMPACT", "cash_flow"),
        (
            "LAND_FEASIBILITY",
            "project_delay",
            "PROJECT_DELIVERY",
            "PROJECT_DELIVERY_SIMULATION",
            "delivery",
        ),
    ],
)
async def test_scenario_and_strategy_use_declared_capabilities(
    dashboard_category,
    scenario_type,
    scenario_category,
    strategy,
    theme,
):
    state = {
        "query": f"Simulate {scenario_type.replace('_', ' ')}",
        "scenario": {
            "scenario_type": scenario_type,
            "target_entity": "Operations",
            "change_type": "increase",
            "change_percentage": 10,
            "time_horizon": "next quarter",
        },
        "dashboard_context": {
            "category": dashboard_category,
            "dashboard_semantics": {
                "capabilities": {
                    "scenario_intent_map": {
                        scenario_type: {
                            "scenario_category": scenario_category,
                            "intent_type": scenario_category,
                            "themes": [theme],
                        },
                    },
                    "scenario_strategy_map": {
                        scenario_type: {
                            "strategy": strategy,
                            "methodology": ["Declared capability methodology"],
                        },
                    },
                },
            },
        },
    }

    await scenario_intent_classifier_node(state)
    assert state["scenario_context"]["scenario_category"] == scenario_category
    assert state["scenario_semantics"]["themes"] == [theme]

    await strategy_selector_node(state)
    assert state["simulation_strategy"] == strategy
    assert state["simulation_strategy_context"]["methodology"] == [
        "Declared capability methodology"
    ]


@pytest.mark.asyncio
async def test_unmapped_scenario_and_domain_terms_do_not_select_strategy():
    state = {
        "query": "GDV HBU handover hurdle scenario",
        "scenario": {
            "scenario_type": "project_delay",
            "description": "GDV HBU handover hurdle",
            "change_type": "increase",
            "change_percentage": 10,
        },
        "dashboard_context": {"category": "LAND_FEASIBILITY"},
    }

    await scenario_intent_classifier_node(state)
    assert state["scenario_context"]["scenario_category"] == "UNCLASSIFIED"
    assert state["scenario_semantics"]["themes"] == []

    await strategy_selector_node(state)
    assert state["simulation_strategy"] == "UNCLASSIFIED"
