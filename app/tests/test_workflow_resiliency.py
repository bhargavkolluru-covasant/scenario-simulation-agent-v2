from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.clients.dashboard_client import DashboardClient
from app.graph.workflow import (
    DEGRADED_STATUS,
    classify_node,
    route_required_node,
    workflow,
)
from app.nodes.explainability_node import explainability_node
from app.nodes.recommendation_node import recommendation_node
from app.nodes.report_generation_node import report_generation_node
from app.nodes.simulation_node import simulation_node
from app.services.explainability_service import ExplainabilityService
from app.services.report_service import ReportService
from app.services.scenario_parser_service import ScenarioParserService
from app.services.simulation_service import SimulationService
from app.api import routes


def _state(**values):
    return {
        "status": "STARTING",
        "degraded_features": [],
        **values,
    }


@pytest.mark.asyncio
async def test_explainability_failure_marks_degraded_feature(monkeypatch):
    monkeypatch.setattr(
        ExplainabilityService,
        "explain",
        AsyncMock(side_effect=RuntimeError("narrative unavailable")),
    )

    result = await classify_node("explainability", explainability_node)(
        _state(simulation_result={}, impact_result={})
    )

    assert result["status"] == DEGRADED_STATUS
    assert result["degraded_features"] == ["explainability"]


@pytest.mark.asyncio
async def test_recommendation_failure_marks_degraded_feature():
    class InvalidActionList(list):
        def __iter__(self):
            raise RuntimeError("recommendation narrative unavailable")

    result = await classify_node("recommendation", recommendation_node)(
        _state(selected_actions=InvalidActionList([{}]))
    )

    assert result["status"] == DEGRADED_STATUS
    assert result["degraded_features"] == ["recommendation_narrative"]


@pytest.mark.asyncio
async def test_dashboard_failure_marks_workflow_failed_and_stops(monkeypatch):
    monkeypatch.setattr(
        ScenarioParserService,
        "parse",
        AsyncMock(return_value={
            "scenario_type": "operational_change",
            "target_entity": "Project delivery",
            "change_type": "increase",
            "change_percentage": 10,
            "time_horizon": "unspecified",
        }),
    )
    monkeypatch.setattr(
        DashboardClient,
        "get_dashboard_context",
        AsyncMock(side_effect=RuntimeError("dashboard unavailable")),
    )

    result = await workflow.ainvoke(
        _state(
            query="Run the scenario",
            dashboard_id="dashboard-test",
            access_token="test-token",
            enterprise_id="enterprise-test",
            domain_ids=["domain-test"],
        )
    )

    assert result["status"] == "FAILED"
    assert result["failed_node"] == "dashboard_intelligence"
    assert result["current_node"] == "dashboard_intelligence"
    assert "final_report" not in result
    assert route_required_node(result) == "stop"


@pytest.mark.asyncio
async def test_simulation_failure_marks_workflow_failed_and_stops(monkeypatch):
    monkeypatch.setattr(
        SimulationService,
        "run",
        AsyncMock(side_effect=RuntimeError("simulation unavailable")),
    )

    result = await classify_node("simulation", simulation_node)(_state())

    assert result["status"] == "FAILED"
    assert result["failed_node"] == "simulation"
    assert route_required_node(result) == "stop"


@pytest.mark.asyncio
async def test_empty_report_is_not_marked_completed():
    async def empty_report_node(state):
        state["status"] = "COMPLETED"
        state["final_report"] = {}
        return state

    result = await classify_node("report", empty_report_node)(_state())

    assert result["status"] == DEGRADED_STATUS
    assert result["degraded_features"] == ["report_enrichment"]


@pytest.mark.asyncio
async def test_report_generation_failure_marks_report_enrichment_degraded(monkeypatch):
    monkeypatch.setattr(
        ReportService,
        "generate_report",
        AsyncMock(side_effect=RuntimeError("report unavailable")),
    )

    result = await classify_node("report", report_generation_node)(_state())

    assert result["status"] == DEGRADED_STATUS
    assert result["degraded_features"] == ["report_enrichment"]


def test_required_failure_response_contains_failed_status(monkeypatch):
    async def failed_workflow(state):
        return {**state, "status": "FAILED"}

    monkeypatch.setattr(routes.workflow, "ainvoke", failed_workflow)
    app = FastAPI()
    app.include_router(routes.router)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/simulation/simulate",
            json={"query": "Run the scenario"},
            headers={
                "Authorization": "Bearer caller-token",
                "X-Enterprise-Id": "enterprise",
                "X-Domain-Id": "domain",
            },
        )

    assert response.status_code == 500
    assert response.json() == {"status": "FAILED"}
