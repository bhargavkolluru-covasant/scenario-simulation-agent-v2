import pytest
from unittest.mock import AsyncMock

from app.clients.rules_client import RulesClient
from app.nodes.rules_node import rules_node
from app.services.root_cause_analysis_service import RootCauseAnalysisService
from app.services.rule_compilation_service import RuleCompilationService
from app.services.rule_relevance_service import filter_relevant_rules


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "category",
        "business_domain",
        "scenario_category",
        "scenario_type",
        "kpi_name",
        "kpi_meaning",
        "kpi_reasoning",
        "risk_name",
        "relevant_rule_name",
        "relevant_rule_terms",
    ),
    [
        (
            "CUSTOMER_EXPERIENCE",
            "customer_experience",
            "CUSTOMER_SATISFACTION",
            "customer_satisfaction_decline",
            "Customer Satisfaction",
            "NPS, review ratings, and customer sentiment feedback.",
            "Customer satisfaction declines as review ratings and NPS fall.",
            "Sentiment Alerts",
            "Customer Satisfaction Sentiment Alert",
            ["Customer Satisfaction", "Sentiment Alerts"],
        ),
        (
            "RETAIL",
            "retail",
            "DEMAND_GROWTH",
            "inventory_demand_increase",
            "Inventory Turnover",
            "Inventory movement and replenishment efficiency.",
            "Inventory movement and replenishment are slowing.",
            "Stockout Risk",
            "Inventory Replenishment Stockout Alert",
            ["Inventory Turnover", "Stockout Risk"],
        ),
        (
            "LOGISTICS",
            "logistics",
            "DEMAND_GROWTH",
            "shipment_demand_increase",
            "On-Time Delivery",
            "Share of shipments delivered on schedule.",
            "Delivery capacity is constrained as shipment volume rises.",
            "Delivery Capacity Risk",
            "On-Time Delivery Capacity Alert",
            ["On-Time Delivery", "Delivery Capacity Risk"],
        ),
    ],
)
async def test_rules_node_keeps_only_relevant_dashboard_rules_as_root_cause_evidence(
    monkeypatch,
    category,
    business_domain,
    scenario_category,
    scenario_type,
    kpi_name,
    kpi_meaning,
    kpi_reasoning,
    risk_name,
    relevant_rule_name,
    relevant_rule_terms,
):
    relevant_rule = {
        "rule_id": f"{business_domain}-relevant",
        "name": relevant_rule_name,
        "description": f"Monitor {' and '.join(relevant_rule_terms)}.",
        "dashboard_category": category,
        "scenario_category": scenario_category,
        "kpi_names": [kpi_name],
        "risk_names": [risk_name],
    }
    unrelated_rules = [
        {
            "rule_id": "lease-expiry",
            "name": "Flag Real Estate Lease Expiry (24 Months)",
            "description": "Review lease term expiry.",
            "category": "REAL_ESTATE",
            "kpi_names": ["Lease Expiry"],
        },
        {
            "rule_id": "loan-facility",
            "name": "Loan Facility Risk: High-Risk Credit Ratings",
            "description": "Monitor loan facility credit exposure.",
            "category": "FINANCE",
            "kpi_names": ["Credit Ratings"],
        },
        {
            "rule_id": "handover-readiness",
            "name": "Handover Readiness Escalation",
            "category": "REAL_ESTATE",
        },
        {
            "rule_id": "gdv-assumptions",
            "name": "GDV Assumption Risk",
            "category": "REAL_ESTATE",
        },
    ]
    monkeypatch.setattr(
        RulesClient,
        "get_rules",
        AsyncMock(return_value={"rules": [*unrelated_rules, relevant_rule]}),
    )
    semantics = {
        "dashboard_name": f"{category.replace('_', ' ').title()} Dashboard",
        "business_domain": business_domain,
        "kpi_definitions": [{
            "name": kpi_name,
            "meaning": kpi_meaning,
        }],
        "risk_groups": [risk_name],
    }
    primary_kpi = {
        "name": kpi_name,
        "reasoning": kpi_reasoning,
        "value": 0.8,
    }
    primary_risk = {
        "name": risk_name,
        "reason": f"{risk_name} is relevant to {kpi_name}.",
    }
    state = {
        "context": {},
        "dashboard_id": f"{business_domain}-dashboard",
        "dashboard_context": {
            "category": category,
            "title": f"{category.replace('_', ' ').title()} Dashboard",
            "dashboard_semantics": semantics,
        },
        "query": f"Assess {scenario_type.replace('_', ' ')}.",
        "scenario": {
            "scenario_type": scenario_type,
            "description": f"Assess {scenario_type.replace('_', ' ')}.",
        },
        "scenario_context": {
            "scenario_category": scenario_category,
            "scenario_type": scenario_type,
        },
        "primary_kpi": primary_kpi,
        "supporting_kpis": [],
        "primary_risk": primary_risk,
        "secondary_risk": None,
    }

    await rules_node(state)

    assert [rule["rule_id"] for rule in state["rules"]] == [
        relevant_rule["rule_id"]
    ]
    findings = RootCauseAnalysisService().analyze(
        scenario=state["scenario"],
        dashboard_data={},
        matched_dashboard_records=[],
        kpi_insights={"kpis": [primary_kpi]},
        rules=[*unrelated_rules, relevant_rule],
        actions=[],
        impact_result={},
        scenario_category=scenario_category,
        primary_kpi=primary_kpi,
        selected_risks=[primary_risk],
        dashboard_context=state["dashboard_context"],
        dashboard_semantics=semantics,
        scenario_context=state["scenario_context"],
    )
    rule_evidence = [
        item
        for finding in findings
        for item in finding["evidence"]
        if item.startswith("Rule:")
    ]
    assert rule_evidence == [f"Rule: {relevant_rule_name}"]
    evidence_text = " ".join(rule_evidence).casefold()
    assert "lease expiry" not in evidence_text
    assert "loan facilities" not in evidence_text
    assert "loan facility risk" not in evidence_text
    assert "handover" not in evidence_text
    assert "gdv" not in evidence_text


def test_unscoped_rules_require_multiple_selected_context_terms():
    state = {
        "dashboard_context": {
            "category": "CUSTOMER_EXPERIENCE",
            "dashboard_semantics": {
                "business_domain": "customer_experience",
                "kpi_definitions": [{
                    "name": "Customer Satisfaction",
                    "meaning": "NPS, review ratings, and customer sentiment.",
                    "aliases": ["Review Ratings", "NPS"],
                }],
            },
        },
        "scenario": {
            "scenario_type": "customer_satisfaction_decline",
            "description": "Customer satisfaction declines.",
        },
        "scenario_context": {
            "scenario_category": "CUSTOMER_SATISFACTION",
        },
        "primary_kpi": {"name": "Customer Satisfaction"},
        "selected_risks": [{"name": "Sentiment Alerts"}],
    }
    rules = [
        {"rule_id": "review-alert", "name": "Review Rating Decline Alert"},
        {
            "rule_id": "loan-facility",
            "name": "Loan Facility Risk: High-Risk Credit Ratings",
        },
        {
            "rule_id": "lease-expiry",
            "name": "Flag Real Estate Lease Expiry (24 Months)",
        },
    ]

    selected = filter_relevant_rules(rules, state)

    assert [rule["rule_id"] for rule in selected] == ["review-alert"]


def test_dashboard_explicit_rule_selection_can_allow_cross_domain_rule():
    rule = {
        "rule_id": "lease-expiry",
        "name": "Flag Real Estate Lease Expiry (24 Months)",
        "category": "REAL_ESTATE",
    }
    state = {
        "dashboard_context": {
            "category": "CUSTOMER_EXPERIENCE",
            "dashboard_semantics": {
                "selected_rule_ids": ["lease-expiry"],
            },
        },
        "primary_kpi": {"name": "Customer Satisfaction"},
    }

    assert filter_relevant_rules([rule], state) == [rule]


@pytest.mark.parametrize(
    ("field", "mismatched_value"),
    [
        ("dashboard_category", "REAL_ESTATE"),
        ("scenario_category", "PROJECT_DELAY"),
        ("kpi_names", ["Loan Facility Risk"]),
        ("risk_names", ["Loan Facility Risk"]),
    ],
)
def test_explicit_rule_scope_mismatch_excludes_rule(field, mismatched_value):
    rule = {
        "rule_id": "scoped-rule",
        "name": "Customer Satisfaction Review Alert",
        "dashboard_category": "CUSTOMER_EXPERIENCE",
        "scenario_category": "CUSTOMER_SATISFACTION",
        "kpi_names": ["Customer Satisfaction"],
        "risk_names": ["Sentiment Alerts"],
    }
    rule[field] = mismatched_value
    state = {
        "dashboard_context": {
            "category": "CUSTOMER_EXPERIENCE",
            "dashboard_semantics": {"business_domain": "customer_experience"},
        },
        "scenario_context": {
            "scenario_category": "CUSTOMER_SATISFACTION",
        },
        "primary_kpi": {"name": "Customer Satisfaction"},
        "primary_risk": {"name": "Sentiment Alerts"},
    }

    assert filter_relevant_rules([rule], state) == []


def test_unclassified_scenario_does_not_discard_dashboard_and_kpi_scoped_rule():
    rule = {
        "rule_id": "customer-satisfaction-rule",
        "name": "Customer Satisfaction Review Alert",
        "dashboard_category": "CUSTOMER_EXPERIENCE",
        "scenario_category": "CUSTOMER_SATISFACTION",
        "kpi_names": ["Customer Satisfaction"],
    }
    state = {
        "dashboard_context": {
            "category": "CUSTOMER_EXPERIENCE",
        },
        "scenario_context": {
            "scenario_category": "UNCLASSIFIED",
        },
        "primary_kpi": {"name": "Customer Satisfaction"},
    }

    assert filter_relevant_rules([rule], state) == [rule]


@pytest.mark.asyncio
async def test_compiled_rules_do_not_default_to_supply_chain_actions_or_domain():
    class OfflineLLM:
        is_configured = False

    service = RuleCompilationService(client=object(), llm_service=OfflineLLM())
    compiled = await service.compile_rule({
        "target_entity": "Customer Support",
        "change_type": "satisfaction decline",
        "change_percentage": 20,
        "time_horizon": "next quarter",
        "business_domain": "customer_experience",
    })

    rule = compiled["rule"]
    assert rule["category"] == "customer_experience"
    assert rule["actions"] == [
        "VALIDATE_SCENARIO_EVIDENCE",
        "NOTIFY_ACCOUNTABLE_OWNER",
    ]
    generic = await service.compile_rule({
        "target_entity": "Business area",
        "change_type": "change",
        "change_percentage": 20,
        "time_horizon": "next quarter",
    })
    assert generic["rule"]["category"] == "UNCLASSIFIED"
    assert generic["rule"]["actions"] == rule["actions"]
