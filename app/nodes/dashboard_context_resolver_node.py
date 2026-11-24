import logging

from app.services.dashboard_intelligence_service import (
    resolve_dashboard_context,
)

from app.state.simulation_state import SimulationState

logger = logging.getLogger(__name__)


async def dashboard_context_resolver_node(
    state: SimulationState,
) -> SimulationState:
    """
    Phase 1

    Dashboard Context Resolver

    Builds both:

    1. Traditional dashboard category
    2. Dashboard semantic understanding

    Downstream nodes should gradually switch
    from dashboard_category to dashboard_semantics.
    """

    logger.info(
        "[dashboard_context_resolver_node] Resolving dashboard context"
    )

    state["current_node"] = (
        "dashboard_context_resolver"
    )

    dashboard_context = resolve_dashboard_context(
        state
    )
    logger.info(
    "[DEBUG] resolved_category=%s",
    dashboard_context.get(
        "category"
    ),
)

    logger.info(
    "[DEBUG] dashboard_semantics=%s",
    dashboard_context.get(
        "dashboard_semantics"
    ),
)

    state["dashboard_context"] = dashboard_context
    for key in (
        "dashboard_category",
        "dashboard_semantics",
        "allowed_kpi_groups",
        "allowed_risk_groups",
        "allowed_action_groups",
        "allowed_kpi_terms",
        "strict_dashboard_filter",
    ):
        state.pop(key, None)

    logger.info(
        "[dashboard_context_resolver_node] category=%s domain=%s themes=%s",
        dashboard_context.get("category"),
        dashboard_context.get(
            "dashboard_semantics",
            {},
        ).get("business_domain"),
        dashboard_context.get(
            "dashboard_semantics",
            {},
        ).get("themes"),
    )

    return state