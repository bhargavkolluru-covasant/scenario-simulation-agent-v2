import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.graph.workflow import workflow

logger = logging.getLogger(__name__)

_API_ERROR_DETAIL = "We couldn't run this simulation right now. Please try again."
_INTERNAL_ERROR_REDACTION = "Internal processing error."
_REPORT_ERROR_REDACTION = "Report generation failed."

security = HTTPBearer()

router = APIRouter(
    prefix="/api/v1/simulation",
    tags=["Simulation"]
)


# =====================================================
# Request / Response Models
# =====================================================

class SimulationRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "What if Horizon Heights handover is delayed by 90 days?",
                "dashboard_id": "dash_3e633ae526ae",
            }
        }
    }

    query: str = Field(
        ...,
        description="Natural language business scenario query"
    )
    dashboard_id: Optional[str] = Field(
        default=None,
        description="Dashboard to use; defaults to DASHBOARD_ID.",
    )


class SimulationResponse(BaseModel):
    status: str

    query: str

    report: Dict[str, Any]

    state: Optional[Dict[str, Any]] = None
    degraded_features: Optional[List[str]] = None


def _sanitize_error_details(value: Any) -> Any:
    if isinstance(value, dict):
        report_failed = value.get("report_id") == "ERR-REPORT"
        sanitized = {}
        for key, item in value.items():
            if isinstance(key, str) and key.lower() == "error":
                sanitized[key] = _INTERNAL_ERROR_REDACTION
            elif report_failed and key == "markdown_report":
                sanitized[key] = _REPORT_ERROR_REDACTION
            else:
                sanitized[key] = _sanitize_error_details(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_error_details(item) for item in value]
    return value


# =====================================================
# Simulation Endpoint
# =====================================================

@router.post(
    "/simulate",
    response_model=SimulationResponse,
    response_model_exclude_none=True,
)
async def run_simulation(
    payload: SimulationRequest,
    include_full_state: bool = Query(
        default=False,
        description="Include complete workflow execution state"
    ),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_enterprise_id: Optional[str] = Header(
        default=None,
        alias="X-Enterprise-Id",
    ),
    x_domain_id: Optional[str] = Header(
        default=None,
        alias="X-Domain-Id",
    ),
):
    """
    Execute end-to-end scenario simulation.

    Workflow:

    Context
        ↓
    Scenario Parser
        ↓
    Dashboard Data
        ↓
    KPI Insights
        ↓
    Actions / NBA
        ↓
    Rules
        ↓
    Knowledge Graph
        ↓
    Simulation
        ↓
    Impact Analysis
        ↓
    Recommendation
        ↓
    Explainability
        ↓
    Report Generation
    """

    logger.info(
        f"[API] Received simulation request: "
        f"query='{payload.query}'"
    )

    # Resolve request context exclusively from caller headers.
    access_token = credentials.credentials
    logger.info(
        "[API] Caller authorization token received: %s",
        bool(access_token),
    )

    enterprise_id = (
        x_enterprise_id.strip()
        if isinstance(x_enterprise_id, str)
        else ""
    )
    raw_domain_ids = (
        x_domain_id
        if isinstance(x_domain_id, str)
        else ""
    )
    domain_ids = [
        domain.strip()
        for domain in raw_domain_ids.split(",")
        if domain.strip()
    ]
    if not enterprise_id or not domain_ids:
        raise HTTPException(
            status_code=400,
            detail="X-Enterprise-Id and X-Domain-Id headers are required.",
        )

    try:
        scope_id = settings.scope_id or ""
        dashboard_id = payload.dashboard_id or settings.DASHBOARD_ID or ""
        logger.info(
            "[API] Executing simulation for enterprise=%s domains=%s",
            enterprise_id,
            domain_ids,
        )

        # -------------------------------------------------
        # Initial State
        # -------------------------------------------------

        initial_state = {

            # User Input
            "query": payload.query,
            "include_full_state": include_full_state,

            # Context
            "context": {
                "enterprise_id": enterprise_id,
                "domain_ids": domain_ids,
                "scope_id": scope_id,
            },
            "access_token": access_token,

            # Tracking
            "status": "STARTING",
            "current_node": "api",
            "error": None,
            "degraded_features": [],

            # Scenario
            "scenario": {},

            # ARIIA platform intelligence
            "semantic_entities": [],
            "dashboard_id": dashboard_id,
            "dashboard_data": {},
            "dashboard_definition": {},
            "dashboard_rows": [],
            "dashboard_context": {},
            "selected_dashboard_kpi_names": [],
            "dashboard_kpi_records": [],
            "causal_support_kpis": [],
            "matched_dashboard_records": [],
            "entity_match_summary": {},
            "kpi_insights": {},
            "actions": [],
            "action_stats": {},
            "knowledge_graph_data": {},

            # Rules
            "rules": [],

            # Simulation Outputs
            "simulation_result": {},
            "impact_result": {},

            # Recommendations
            "recommendations": [],

            # Explainability
            "explanation": {},

            # Final Output
            "final_report": {},
        }

        # -------------------------------------------------
        # Execute Workflow
        # -------------------------------------------------

        result_state = await workflow.ainvoke(
            initial_state
        )

        final_report = result_state.get(
            "final_report",
            {}
        )
        final_report = _sanitize_error_details(final_report)
        if not isinstance(final_report, dict):
            final_report = {}

        status = result_state.get(
            "status",
            "FAILED",
        )
        degraded_features = result_state.get("degraded_features", [])
        if not isinstance(degraded_features, list):
            degraded_features = []
        report_is_empty = (
            not isinstance(final_report, dict)
            or not str(final_report.get("markdown_report") or "").strip()
        )
        if report_is_empty:
            if status in {"COMPLETED", "COMPLETED_WITH_DEGRADED_FEATURES"}:
                status = "COMPLETED_WITH_DEGRADED_FEATURES"
                if "report_enrichment" not in degraded_features:
                    degraded_features.append("report_enrichment")
            else:
                status = "FAILED"

        if status == "FAILED":
            return JSONResponse(
                status_code=500,
                content={"status": "FAILED"},
            )

        response = {
            "status": status,
            "query": payload.query,
            "report": final_report,
        }
        if degraded_features:
            response["degraded_features"] = degraded_features

        if include_full_state:
            response_state = _sanitize_error_details(dict(result_state))
            if response_state.get("access_token"):
                response_state["access_token"] = "******"
            simulation_result = response_state.get("simulation_result")
            metrics = (
                simulation_result.get("metrics")
                if isinstance(simulation_result, dict)
                else None
            )
            financial_model = (
                metrics.get("financial_model")
                if isinstance(metrics, dict)
                else None
            )
            scenario_exposure = (
                financial_model.get("scenario_exposure")
                if isinstance(financial_model, dict)
                else None
            )
            if not isinstance(scenario_exposure, dict):
                scenario_exposure = {}
            response_state["baseline_selection"] = {
                "primary_baseline": scenario_exposure.get("primary_baseline"),
                "alternative_baselines": scenario_exposure.get(
                    "alternative_baselines",
                    [],
                ),
            }
            response["state"] = response_state

        logger.info(
            f"[API] Simulation completed "
            f"with status={status}"
        )

        return response

    except Exception as exc:
        request_id = str(uuid.uuid4())
        status_code = (
            exc.status_code
            if isinstance(exc, HTTPException)
            else 500
        )

        logger.exception(
            "[API] Simulation execution failed. request_id=%s",
            request_id,
        )

        return JSONResponse(
            status_code=status_code,
            content={
                "detail": _API_ERROR_DETAIL,
                "request_id": request_id,
            },
        )