import copy
import json

import pytest

from app.nodes.context_node import context_node
from app.nodes.dashboard_context_resolver_node import dashboard_context_resolver_node
from app.nodes.risk_selector_node import risk_selector_node
from app.nodes.scenario_intent_classifier_node import scenario_intent_classifier_node
from app.nodes.action_selector_node import action_selector_node
from app.services.report_service import ReportService


@pytest.mark.asyncio
async def test_state_owners_remove_duplicate_copies_reduce_size_and_keep_report_fields():
    duplicate_semantics = {
        "themes": ["revenue", "growth"],
        "intent_summary": "Revenue increases by 20% next quarter.",
        "intent_type": "REVENUE_GROWTH",
    }
    duplicate_dashboard_semantics = {
        "themes": ["finance"],
        "widget_titles": ["Revenue Actual vs Forecast"],
        "business_domain": "Finance",
    }
    duplicate_reasoning = {
        "primary_risk": {"name": "Revenue Risk", "severity": "MEDIUM"},
        "secondary_risk": None,
        "actions": [{"title": "Monitor revenue performance"}],
    }
    state = {
        "query": "Revenue increases by 20% next quarter.",
        "enterprise_id": "enterprise-1",
        "domain_ids": ["finance"],
        "scope_id": "scope-1",
        "context": {
            "enterprise_id": "enterprise-1",
            "domain_ids": ["finance"],
            "scope_id": "scope-1",
        },
        "scenario": {
            "scenario_type": "revenue_change",
            "target_entity": "Revenue",
            "change_type": "increase",
            "change_percentage": 20,
            "time_horizon": "next quarter",
        },
        "scenario_context": {"scenario_semantics": duplicate_semantics},
        "scenario_semantics": duplicate_semantics,
        "dashboard_definition": {
            "title": "Finance Dashboard",
            "widgets": [{"title": "Revenue Actual vs Forecast"}],
        },
        "dashboard_data": {
            "widgets": [{
                "title": "Revenue Actual vs Forecast",
                "data": {"rows": [{"name": "Revenue Actual", "value": 10_000_000}]},
            }],
        },
        "dashboard_context": {
            "title": "Finance Dashboard",
            "category": "FINANCE",
            "dashboard_semantics": duplicate_dashboard_semantics,
            "allowed_kpi_groups": ["cash flow", "revenue and margin"],
            "allowed_kpi_terms": ["Revenue Actual"],
        },
        "semantic_reasoning": duplicate_reasoning,
        "risk_context": {
            "primary_risk": duplicate_reasoning["primary_risk"],
            "secondary_risk": None,
            "source": "semantic_reasoning",
        },
        "dashboard_category": "FINANCE",
        "dashboard_semantics": duplicate_dashboard_semantics,
        "allowed_kpi_groups": ["cash flow", "revenue and margin"],
        "allowed_risk_groups": ["Liquidity Risk"],
        "allowed_action_groups": ["Cash flow protection"],
        "allowed_kpi_terms": ["Revenue Actual"],
        "strict_dashboard_filter": True,
    }
    await context_node(state)
    await scenario_intent_classifier_node(state)
    await dashboard_context_resolver_node(state)
    await risk_selector_node(state)
    await action_selector_node(state)

    after_size = len(json.dumps(state, separators=(",", ":"), sort_keys=True))
    legacy_state = copy.deepcopy(state)
    legacy_state.update({
        "enterprise_id": state["context"]["enterprise_id"],
        "domain_ids": state["context"]["domain_ids"],
        "scope_id": state["context"]["scope_id"],
        "scenario_semantics": copy.deepcopy(state["scenario_semantics"]),
        "dashboard_category": state["dashboard_context"]["category"],
        "dashboard_semantics": copy.deepcopy(
            state["dashboard_context"]["dashboard_semantics"]
        ),
        "allowed_kpi_groups": copy.deepcopy(
            state["dashboard_context"]["allowed_kpi_groups"]
        ),
        "allowed_risk_groups": copy.deepcopy(
            state["dashboard_context"]["allowed_risk_groups"]
        ),
        "allowed_action_groups": copy.deepcopy(
            state["dashboard_context"]["allowed_action_groups"]
        ),
        "allowed_kpi_terms": copy.deepcopy(
            state["dashboard_context"]["allowed_kpi_terms"]
        ),
        "strict_dashboard_filter": state["dashboard_context"]["category_resolved"],
        "semantic_reasoning": copy.deepcopy(duplicate_reasoning),
        "risk_context": {
            "primary_risk": copy.deepcopy(duplicate_reasoning["primary_risk"]),
            "secondary_risk": None,
            "source": "semantic_reasoning",
        },
    })
    legacy_state["scenario_context"]["scenario_semantics"] = copy.deepcopy(
        state["scenario_semantics"]
    )
    before_size = len(
        json.dumps(legacy_state, separators=(",", ":"), sort_keys=True)
    )
    assert after_size < before_size

    assert state["context"] == {
        "enterprise_id": "enterprise-1",
        "domain_ids": ["finance"],
        "scope_id": "scope-1",
    }
    assert not {"enterprise_id", "domain_ids", "scope_id"} & state.keys()
    assert state["scenario"]
    assert state["scenario_semantics"]["themes"]
    assert "scenario_semantics" not in state["scenario_context"]
    assert state["scenario_context"]["scenario_category"]
    assert state["scenario_context"]["decision_type"]
    assert state["dashboard_data"]
    assert state["dashboard_context"]["category"] == "FINANCE"
    assert state["dashboard_context"]["dashboard_semantics"]
    assert state["primary_risk"] == duplicate_reasoning["primary_risk"]
    assert state["selected_actions"] == duplicate_reasoning["actions"]
    assert "risk_context" not in state
    assert "semantic_reasoning" not in state
    assert not {
        "dashboard_category",
        "dashboard_semantics",
        "allowed_kpi_groups",
        "allowed_risk_groups",
        "allowed_action_groups",
        "allowed_kpi_terms",
        "strict_dashboard_filter",
    } & state.keys()

    report_state = {
        **state,
        "primary_kpi": {"name": "Revenue Actual", "value": "AED 10M"},
        "primary_risk": {"name": "Revenue Risk", "severity": "MEDIUM"},
        "selected_actions": [{"title": "Monitor revenue performance"}],
    }
    report = await ReportService().generate_report(report_state)
    assert "Executive Scenario Report" in report["markdown_report"]
    assert report["dashboard_context"] == {"title": "Finance Dashboard"}
