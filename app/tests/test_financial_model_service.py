import pytest

from app.services.financial_model_service import (
    IMPACT_MODEL_REGISTRY,
    FinancialModelService,
    classify_kpi,
)
from app.services.impact_analysis_service import ImpactAnalysisService
from app.services.recommendation_service import RecommendationService
from app.services.report_service import ReportService
from app.services.simulation_service import SimulationService


@pytest.mark.parametrize(
    ("record", "expected_category"),
    [
        ({"kpi_name": "Customer experience score"}, "CUSTOMER"),
        ({"metric_name": "Cash flow margin"}, "FINANCIAL"),
        ({"title": "Production throughput"}, "OPERATIONAL"),
        ({"label": "Regulatory violations"}, "COMPLIANCE"),
        ({"description": "Business continuity exposure"}, "RISK"),
        ({"reasoning": "Strategic market growth objective"}, "STRATEGIC"),
    ],
)
def test_kpi_classification_uses_semantic_fields(record, expected_category):
    assert classify_kpi(record) == expected_category


@pytest.mark.parametrize(
    ("scenario", "kpi", "category", "direction"),
    [
        (
            {
                "query": "What if customer satisfaction drops?",
                "domain": "Customer Experience",
            },
            {"kpi_name": "Customer satisfaction score", "kpi_value": 4.1},
            "CUSTOMER",
            "DECREASE",
        ),
        (
            "What if cash flow decreases by 10%?",
            {
                "kpi_name": "Cash flow",
                "kpi_value": 2_000_000,
                "kpi_unit": "AED",
                "confidence_score": 0.9,
                "business_importance": "HIGH",
            },
            "FINANCIAL",
            "DECREASE",
        ),
        (
            "What if production throughput decreases?",
            {
                "kpi_name": "Production throughput",
                "kpi_value": 95,
                "kpi_unit": "%",
                "confidence_score": 0.8,
            },
            "OPERATIONAL",
            "DECREASE",
        ),
        (
            "What if compliance violations rise?",
            {
                "kpi_name": "Regulatory violations",
                "kpi_value": 3,
                "confidence_score": 0.95,
            },
            "COMPLIANCE",
            "INCREASE",
        ),
        (
            "What if inventory shortages increase by 20%?",
            {
                "kpi_name": "Inventory shortages",
                "kpi_value": 50,
                "confidence_score": 0.75,
            },
            "OPERATIONAL",
            "INCREASE",
        ),
        (
            "What if enterprise incident risk increases?",
            {
                "kpi_name": "Enterprise incident risk",
                "kpi_value": 0.25,
                "confidence_score": 0.85,
            },
            "RISK",
            "INCREASE",
        ),
    ],
)
def test_generic_scenario_model_classifies_direction_and_risk(
    scenario, kpi, category, direction
):
    result = FinancialModelService().model(
        scenario=scenario,
        dashboard_data={},
        kpi_insights={"kpis": [kpi]},
        actions=[],
        rules=[],
    )
    modeled = result["scenario_exposure"]

    assert modeled["direction"] == direction
    assert category in modeled["affected_categories"]
    assert modeled["impacts"]
    if "confidence_score" in kpi:
        assert modeled["confidence"] > 0
    else:
        assert modeled["confidence"] is None
        assert modeled["confidence_reason"]
    assert modeled["financial_reasoning"]
    assert modeled["assumptions"]
    assert result["confidence"] == modeled["confidence"]
    assert result["combined_outlook"]["risk_dimensions"]


def test_percent_change_estimates_only_matched_monetary_kpi_and_keeps_current_exposure_separate():
    result = FinancialModelService().model(
        scenario="What if cash flow decreases by 10%?",
        dashboard_data={},
        kpi_insights={
            "kpis": [
                {
                    "kpi_name": "Cash flow",
                    "kpi_value": 2_000_000,
                    "kpi_unit": "AED",
                    "confidence_score": 0.9,
                },
                {
                    "kpi_name": "Outstanding receivable exposure",
                    "kpi_value": 500_000,
                    "kpi_unit": "AED",
                },
            ]
        },
        actions=[],
        rules=[],
    )

    assert result["current_exposure"]["total_by_currency"]["AED"] == 500_000
    assert result["scenario_exposure"]["estimated_amount_by_currency"]["AED"] == 200_000
    assert result["scenario_exposure"]["amount_evidence"][0]["kpi"] == "Cash flow"
    estimate = result["scenario_exposure"]["amount_evidence"][0]
    assert estimate["why"]
    assert "×" in estimate["derivation"]
    assert estimate["assumptions"]
    assert "total_by_currency" not in result["combined_outlook"]
    assert "not added together" in result["combined_outlook"]["summary"]
    assert set(result) == {
        "current_exposure",
        "scenario_exposure",
        "combined_outlook",
        "confidence",
        "confidence_reason",
    }


@pytest.mark.parametrize(
    ("name", "scenario"),
    [
        (
            "Cashflow",
            "What if cashflow actual and cashflow forecast fall by 10%?",
        ),
        (
            "Revenue",
            "What if revenue actual and revenue forecast fall by 10%?",
        ),
        (
            "Collections",
            "What if collections actual and collections forecast fall by 10%?",
        ),
    ],
)
@pytest.mark.asyncio
async def test_simulation_uses_one_ranked_baseline_for_actual_and_forecast_kpis(name, scenario):
    actual_name = f"{name} Actual"
    forecast_name = f"{name} Forecast"
    state = {
        "query": scenario,
        "scenario": {"query": scenario, "change_percentage": 10},
        "dashboard_data": {},
        "dashboard_rows": [],
        "matched_dashboard_records": [],
        "kpi_insights": {"kpis": [
            {
                "kpi_name": actual_name,
                "kpi_value": 10_000_000,
                "kpi_unit": "AED",
            },
            {
                "kpi_name": forecast_name,
                "kpi_value": 8_000_000,
                "kpi_unit": "AED",
            },
        ]},
        "dashboard_kpi_records": [
            {
                "name": actual_name,
                "value": 10_000_000,
                "_scoring": {
                    "semantic_relevance": 0.9,
                    "dashboard_relevance": 0.8,
                },
            },
            {
                "name": forecast_name,
                "value": 8_000_000,
                "_scoring": {
                    "semantic_relevance": 0.4,
                    "dashboard_relevance": 1.0,
                },
            },
        ],
        "actions": [],
        "action_stats": {},
        "rules": [],
        "knowledge_graph_data": {},
    }

    simulation = await SimulationService().run(state)
    exposure = simulation["financial_model"]["scenario_exposure"]

    assert exposure["primary_baseline"]["name"] == actual_name
    assert exposure["primary_baseline"]["value"] == 10_000_000
    assert [item["name"] for item in exposure["alternative_baselines"]] == [
        forecast_name
    ]
    assert exposure["estimated_amount_by_currency"] == {"AED": 1_000_000}
    assert [item["kpi"] for item in exposure["amount_evidence"]] == [actual_name]
    assert simulation["metrics"]["scenario_incremental_financial_exposure"] == 1_000_000


@pytest.mark.parametrize(
    ("actual_scores", "forecast_scores", "actual_confidence", "forecast_confidence", "expected"),
    [
        (
            {"semantic_relevance": 0.8, "dashboard_relevance": 0.1, "match_score": 0.1},
            {"semantic_relevance": 0.7, "dashboard_relevance": 1.0, "match_score": 1.0},
            0.1,
            1.0,
            "Revenue Actual",
        ),
        (
            {"semantic_relevance": 0.8, "dashboard_relevance": 0.4, "match_score": 1.0},
            {"semantic_relevance": 0.8, "dashboard_relevance": 0.6, "match_score": 0.1},
            1.0,
            0.1,
            "Revenue Forecast",
        ),
        (
            {"semantic_relevance": 0.8, "dashboard_relevance": 0.5, "match_score": 0.4},
            {"semantic_relevance": 0.8, "dashboard_relevance": 0.5, "match_score": 0.6},
            1.0,
            0.1,
            "Revenue Forecast",
        ),
        (
            {"semantic_relevance": 0.8, "dashboard_relevance": 0.5, "match_score": 0.6},
            {"semantic_relevance": 0.8, "dashboard_relevance": 0.5, "match_score": 0.6},
            0.1,
            1.0,
            "Revenue Forecast",
        ),
    ],
)
def test_baseline_selection_uses_semantic_dashboard_match_then_confidence_priority(
    actual_scores,
    forecast_scores,
    actual_confidence,
    forecast_confidence,
    expected,
):
    result = FinancialModelService().model(
        scenario="What if revenue actual and revenue forecast fall by 10%?",
        dashboard_data={},
        kpi_insights={"kpis": [
            {
                "kpi_name": "Revenue Actual",
                "kpi_value": 10_000_000,
                "kpi_unit": "AED",
                "confidence_score": actual_confidence,
                "_scoring": actual_scores,
            },
            {
                "kpi_name": "Revenue Forecast",
                "kpi_value": 8_000_000,
                "kpi_unit": "AED",
                "confidence_score": forecast_confidence,
                "_scoring": forecast_scores,
            },
        ]},
        actions=[],
        rules=[],
    )

    assert result["scenario_exposure"]["primary_baseline"]["name"] == expected


def test_current_financial_exposure_uses_generic_financial_risk_signals():
    result = FinancialModelService().model(
        scenario="Assess current risk",
        dashboard_data={},
        kpi_insights={
            "kpis": [
                {"kpi_name": "Budget overrun", "kpi_value": 1000, "kpi_unit": "AED"},
                {"kpi_name": "Pending clawback", "kpi_value": 300, "kpi_unit": "AED"},
                {"kpi_name": "Cash revenue", "kpi_value": 900, "kpi_unit": "AED"},
            ]
        },
        actions=[],
        rules=[],
    )

    items = result["current_exposure"]["items"]
    assert {item["name"] for item in items} == {"Budget overrun", "Pending clawback"}
    assert result["scenario_exposure"]["estimated_amount_by_currency"] == {}
    assert "total_by_currency" not in result["combined_outlook"]


def test_kpi_confidence_and_business_importance_change_model_confidence_and_severity():
    service = FinancialModelService()

    def run(confidence, importance):
        return service.model(
            scenario="What if production throughput decreases by 20%?",
            dashboard_data={},
            kpi_insights={
                "kpis": [{
                    "kpi_name": "Production throughput",
                    "kpi_value": 90,
                    "confidence_score": confidence,
                    "business_importance": importance,
                }]
            },
            actions=[],
            rules=[],
        )

    low_evidence = run(0.1, 0.1)
    high_evidence = run(0.95, 0.95)

    assert high_evidence["confidence"] > low_evidence["confidence"]
    assert (
        high_evidence["scenario_exposure"]["severity"]
        != low_evidence["scenario_exposure"]["severity"]
    )


def test_missing_confidence_and_importance_remain_unavailable():
    result = FinancialModelService().model(
        scenario="What if production throughput decreases by 20%?",
        dashboard_data={},
        kpi_insights={"kpis": [{
            "kpi_name": "Production throughput",
            "kpi_value": 90,
        }]},
        actions=[],
        rules=[],
    )

    scenario = result["scenario_exposure"]
    assert scenario["confidence"] is None
    assert scenario["confidence_reason"]
    driver = scenario["impact_drivers"][0]
    assert driver["confidence"] is None
    assert driver["confidence_reason"]
    assert driver["business_importance"] is None
    assert driver["business_importance_reason"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kpis",
    [
        {},
        {"kpis": [{"kpi_name": "Cash flow", "kpi_value": 100}]},
    ],
)
async def test_simulation_does_not_invent_risk_metrics_without_a_risk_kpi(kpis):
    simulation = await SimulationService().run({
        "query": "Assess enterprise risk",
        "scenario": {},
        "dashboard_data": {},
        "kpi_insights": kpis,
        "actions": [],
        "action_stats": {},
        "rules": [],
        "knowledge_graph_data": {},
    })

    metrics = simulation["metrics"]
    assert metrics["risk_score"] is None
    assert metrics["risk_score_reason"]
    assert metrics["impact_probability"] is None
    assert metrics["impact_probability_reason"]


def test_impact_registry_covers_each_business_category():
    assert set(IMPACT_MODEL_REGISTRY) == {
        "CUSTOMER",
        "FINANCIAL",
        "OPERATIONAL",
        "COMPLIANCE",
        "RISK",
        "STRATEGIC",
    }
    assert all(IMPACT_MODEL_REGISTRY.values())


@pytest.mark.asyncio
async def test_simulation_and_impact_never_use_current_kpi_exposure_as_scenario_loss():
    state = {
        "query": "What if customer satisfaction drops?",
        "scenario": {"query": "What if customer satisfaction drops?"},
        "dashboard_data": {},
        "dashboard_rows": [],
        "matched_dashboard_records": [],
        "kpi_insights": {
            "kpis": [{
                "kpi_name": "Unpaid commission exposure",
                "kpi_value": 25_234_246,
                "kpi_unit": "AED",
            }]
        },
        "actions": [],
        "action_stats": {},
        "rules": [],
        "knowledge_graph_data": {},
    }
    simulation = await SimulationService().run(state)
    state["simulation_result"] = simulation
    impact = await ImpactAnalysisService().analyze(state)

    assert simulation["financial_model"]["current_exposure"]["total_by_currency"]["AED"] == 25_234_246
    assert simulation["financial_model"]["scenario_exposure"]["estimated_amount_by_currency"] == {}
    assert simulation["metrics"]["scenario_incremental_financial_exposure"] == 0
    assert impact["financial_exposure_at_risk"] == 0
    assert impact["financial_exposure_source"] == "unquantified"
    assert impact["financial_exposure_evidence"][0]["category"] == "Current Enterprise Exposure"


@pytest.mark.asyncio
async def test_simulation_metric_does_not_add_existing_and_incremental_exposure():
    simulation = await SimulationService().run({
        "query": "What if cash flow decreases by 10%?",
        "scenario": {
            "query": "What if cash flow decreases by 10%?",
            "change_percentage": 10,
        },
        "dashboard_data": {},
        "dashboard_rows": [],
        "matched_dashboard_records": [],
        "kpi_insights": {"kpis": [
            {
                "kpi_name": "Cash flow",
                "kpi_value": 2_000_000,
                "kpi_unit": "AED",
            },
            {
                "kpi_name": "Outstanding receivable exposure",
                "kpi_value": 500_000,
                "kpi_unit": "AED",
            },
        ]},
        "actions": [],
        "action_stats": {},
        "rules": [],
        "knowledge_graph_data": {},
    })

    metrics = simulation["metrics"]
    assert metrics["baseline_financial_exposure"] == 500_000
    assert metrics["scenario_incremental_financial_exposure"] == 200_000
    assert metrics["simulated_financial_exposure"] == 200_000


@pytest.mark.asyncio
async def test_report_renders_generic_current_and_scenario_financial_views():
    financial_model = FinancialModelService().model(
        scenario="What if cash flow decreases by 10%?",
        dashboard_data={},
        kpi_insights={
            "kpis": [{
                "kpi_name": "Cash flow",
                "kpi_value": 2_000_000,
                "kpi_unit": "AED",
                "confidence_score": 0.9,
            }]
        },
        actions=[],
        rules=[],
    )
    report = await ReportService().generate_report({
        "query": "What if cash flow decreases by 10%?",
        "scenario": {},
        "simulation_result": {"financial_model": financial_model, "metrics": {}},
        "impact_result": {"financial_model": financial_model},
        "kpi_insights": {},
        "knowledge_graph_data": {"nodes": [], "edges": []},
        "include_full_state": True,
    })

    assert report["financial_impact"] is None
    assert "## Financial Impact" not in report["markdown_report"]
    assert "Current Enterprise Exposure" not in report["markdown_report"]
    assert "Cash Flow Risk" not in report["markdown_report"]


@pytest.mark.asyncio
async def test_default_report_hides_financial_model_details():
    financial_model = FinancialModelService().model(
        scenario="What if cash flow decreases by 10%?",
        dashboard_data={},
        kpi_insights={"kpis": [{
            "kpi_name": "Cash flow",
            "kpi_value": 2_000_000,
            "kpi_unit": "AED",
            "confidence_score": 0.9,
        }]},
        actions=[],
        rules=[],
    )
    report = await ReportService().generate_report({
        "query": "What if cash flow decreases by 10%?",
        "simulation_result": {"financial_model": financial_model},
        "impact_result": {"financial_model": financial_model},
    })

    assert report["financial_impact"] is None
    assert "## Financial Impact" not in report["markdown_report"]


@pytest.mark.asyncio
async def test_recommendation_forwards_only_selector_owned_actions():
    recommendations = await RecommendationService().generate_recommendations({
        "actions": [{"title": "Unselected catalog action"}],
        "selected_actions": [{"title": "Selected semantic action"}],
        "simulation_result": {
            "metrics": {"impact_probability": 0.5},
            "financial_model": {
                "scenario_exposure": {
                    "estimated_amount_by_currency": {"AED": 200_000},
                }
            },
            "target_entities": ["Operations"],
        },
    })

    assert recommendations == [{"title": "Selected semantic action"}]
