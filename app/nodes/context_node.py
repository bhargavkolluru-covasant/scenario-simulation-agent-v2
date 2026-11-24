import logging

from app.config.settings import settings
from app.state.simulation_state import SimulationState

logger = logging.getLogger(__name__)


class ContextInitializationError(Exception):
    """Raised when execution context cannot be initialized."""
    pass


async def context_node(
    state: SimulationState
) -> SimulationState:
    """
    LangGraph Node: Context Initialization

    Purpose:
    - Initialize execution context
    - Resolve the active enterprise and domain
    - Populate state context
    - Provide a consistent execution environment
      for downstream nodes

    NOTE:
    Enterprise and Domain are already selected
    by the ARIIA platform before the user enters
    the agent.

    Scope is retained as optional backward-compatible context.
    """

    logger.info(
        "[context_node] Initializing execution context"
    )

    state["current_node"] = "context"

    try:
        context = state.get("context")
        if not isinstance(context, dict):
            context = {}
        enterprise_id = (
            context.get("enterprise_id")
            or state.get("enterprise_id")
            or settings.enterprise_id
        )
        domain_ids = (
            context.get("domain_ids")
            or state.get("domain_ids")
            or settings.domain_ids
        )
        scope_id = (
            context.get("scope_id")
            or state.get("scope_id")
            or settings.scope_id
            or ""
        )

        if not enterprise_id or not domain_ids:
            raise ContextInitializationError(
                "ARIIA enterprise_id and domain_ids are required."
            )

        state["context"] = {
            "enterprise_id": enterprise_id,
            "domain_ids": domain_ids,
            "scope_id": scope_id,
        }
        for key in ("enterprise_id", "domain_ids", "scope_id"):
            state.pop(key, None)

        logger.info(
            "[context_node] Context initialized for enterprise=%s domains=%s",
            enterprise_id,
            domain_ids,
        )

    except Exception as exc:

        logger.error(
            "[context_node] Context initialization "
            f"failed: {exc}"
        )

        state["error"] = str(exc)
        state["status"] = "FAILED"

        raise

    return state