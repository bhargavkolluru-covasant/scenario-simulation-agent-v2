import logging
import uuid

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes
from app.clients import base_client
from app.clients.base_client import BaseClient
from app.clients.dashboard_client import DashboardClient
from app.config.settings import Settings


def test_simulation_request_context_is_used_for_workflow(monkeypatch, caplog):
    received_state = {}
    caplog.set_level(logging.INFO)

    async def fake_ainvoke(state):
        received_state.update(state)
        return {
            **state,
            "final_report": {},
            "status": "COMPLETED",
        }

    monkeypatch.setattr(routes.workflow, "ainvoke", fake_ainvoke)
    app = FastAPI()
    app.include_router(routes.router)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/simulation/simulate",
            json={
                "query": "What if Horizon Heights handover is delayed by 90 days?",
                "dashboard_id": "dash-request",
                "enterprise_id": "body-enterprise",
                "domain_ids": ["body-domain"],
                "scope_id": "body-scope",
                "access_token": "Bearer body-token",
            },
            headers={
                "Authorization": "Bearer request-token",
                "X-Enterprise-Id": "ent-request",
                "X-Domain-Id": "domain-one, domain-two",
            },
            params={"include_full_state": "true"},
        )

    assert response.status_code == 200
    response_body = response.json()
    assert received_state["access_token"] == "request-token"
    assert received_state["dashboard_id"] == "dash-request"
    assert received_state["enterprise_id"] == "ent-request"
    assert received_state["domain_ids"] == ["domain-one", "domain-two"]
    assert "domain_id" not in received_state
    assert received_state["include_full_state"] is True
    assert response_body["state"]["access_token"] == "******"
    assert "Caller authorization token received: True" in caplog.text
    assert "request-token" not in caplog.text

    headers = DashboardClient(
        auth_token=received_state["access_token"],
        enterprise_id=received_state["enterprise_id"],
        domain_ids=received_state["domain_ids"],
    )._get_headers()
    assert headers["Authorization"] == "Bearer request-token"
    assert headers["X-Enterprise-Id"] == "ent-request"
    assert headers["X-Domain-Id"] == "domain-one,domain-two"


def test_simulation_request_schema_includes_frontend_example():
    example = routes.SimulationRequest.model_json_schema()["example"]

    assert example == {
        "query": "What if Horizon Heights handover is delayed by 90 days?",
        "dashboard_id": "dash_3e633ae526ae",
    }

    assert set(routes.SimulationRequest.model_fields) == {
        "query",
        "dashboard_id",
    }


def test_enterprise_id_has_no_builtin_default(monkeypatch):
    monkeypatch.delenv("ARIIA_ENTERPRISE_ID", raising=False)

    assert Settings(_env_file=None).enterprise_id == ""


def test_simulation_requires_authorization_header():
    app = FastAPI()
    app.include_router(routes.router)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/simulation/simulate",
            json={"query": "Run the scenario"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_simulation_openapi_declares_bearer_authentication():
    app = FastAPI()
    app.include_router(routes.router)

    schema = app.openapi()
    operation = schema["paths"]["/api/v1/simulation/simulate"]["post"]

    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    assert operation["security"] == [{"HTTPBearer": []}]


@pytest.mark.parametrize(
    ("enterprise_id", "domain_ids"),
    [
        (None, "domain"),
        ("enterprise", None),
        ("enterprise", " , "),
    ],
)
def test_simulation_requires_tenant_headers(enterprise_id, domain_ids):
    app = FastAPI()
    app.include_router(routes.router)
    headers = {"Authorization": "Bearer caller-token"}
    if enterprise_id is not None:
        headers["X-Enterprise-Id"] = enterprise_id
    if domain_ids is not None:
        headers["X-Domain-Id"] = domain_ids

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/simulation/simulate",
            json={"query": "Run the scenario"},
            headers=headers,
        )

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("failure_source", "expected_status"),
    [
        ("node", 500),
        ("http_client", 500),
        ("workflow", 500),
        ("workflow_http", 401),
    ],
)
def test_simulation_failure_returns_generic_error(
    monkeypatch,
    caplog,
    failure_source,
    expected_status,
):
    async def failing_ainvoke(state):
        assert state["query"] == "Run the scenario"
        if failure_source == "node":
            async def failing_node():
                raise RuntimeError(
                    "node failed at https://internal.example/private"
                )

            await failing_node()
        elif failure_source == "http_client":
            request = httpx.Request(
                "GET",
                "https://platform.internal/private",
            )
            response = httpx.Response(
                502,
                request=request,
                text="upstream authentication details",
            )
            raise httpx.HTTPStatusError(
                "502 Bad Gateway",
                request=request,
                response=response,
            )
        elif failure_source == "workflow_http":
            raise routes.HTTPException(
                status_code=401,
                detail="Internal authentication failure at https://private",
            )
        raise RuntimeError("workflow stack and secret details")

    monkeypatch.setattr(routes.workflow, "ainvoke", failing_ainvoke)
    caplog.set_level(logging.ERROR, logger=routes.logger.name)
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

    response_body = response.json()
    assert response.status_code == expected_status
    assert response_body["detail"] == (
        "We couldn't run this simulation right now. Please try again."
    )
    request_id = response_body["request_id"]
    assert str(uuid.UUID(request_id)) == request_id
    assert set(response_body) == {"detail", "request_id"}
    for sensitive_text in (
        "internal.example",
        "platform.internal",
        "upstream authentication details",
        "workflow stack",
        "Internal authentication failure",
    ):
        assert sensitive_text not in response.text
    assert any(
        request_id in record.getMessage() and record.exc_info
        for record in caplog.records
    )


def test_full_state_redacts_node_and_report_exceptions(monkeypatch):
    raw_exception = "upstream auth failed at https://internal.example/private"

    async def fake_ainvoke(state):
        return {
            **state,
            "status": "COMPLETED_WITH_DEGRADED_FEATURES",
            "degraded_features": ["report_enrichment"],
            "error": raw_exception,
            "simulation_result": {"error": raw_exception},
            "final_report": {
                "report_id": "ERR-REPORT",
                "error": raw_exception,
                "markdown_report": f"Report failed: {raw_exception}",
            },
        }

    monkeypatch.setattr(routes.workflow, "ainvoke", fake_ainvoke)
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
            params={"include_full_state": "true"},
        )

    response_body = response.json()
    assert response.status_code == 200
    assert response_body["status"] == "COMPLETED_WITH_DEGRADED_FEATURES"
    assert response_body["degraded_features"] == ["report_enrichment"]
    assert raw_exception not in response.text
    assert response_body["report"]["error"] == "Internal processing error."
    assert response_body["report"]["markdown_report"] == "Report generation failed."
    assert response_body["state"]["error"] == "Internal processing error."
    assert (
        response_body["state"]["simulation_result"]["error"]
        == "Internal processing error."
    )


@pytest.mark.asyncio
async def test_base_client_does_not_log_upstream_response_body(
    monkeypatch,
    caplog,
):
    upstream_secret = "upstream private response body"

    class FailingAsyncClient:
        def __init__(self, timeout):
            assert timeout > 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return not any(exc_info)

        async def get(self, url, **kwargs):
            assert "params" in kwargs
            assert "headers" in kwargs
            request = httpx.Request("GET", url)
            response = httpx.Response(
                502,
                request=request,
                text=upstream_secret,
            )
            raise httpx.HTTPStatusError(
                "Bad gateway",
                request=request,
                response=response,
            )

    monkeypatch.setattr(base_client.httpx, "AsyncClient", FailingAsyncClient)
    caplog.set_level(logging.ERROR, logger=base_client.logger.name)

    with pytest.raises(httpx.HTTPStatusError):
        await BaseClient("https://platform.internal").get("/resource")

    assert upstream_secret not in caplog.text
    assert "502" in caplog.text
