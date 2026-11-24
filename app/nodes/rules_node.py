import logging
from typing import Any, Dict, List
from app.clients.rules_client import RulesClient
from app.services.rule_relevance_service import filter_relevant_rules
from app.state.simulation_state import SimulationState

logger = logging.getLogger(__name__)


async def rules_node(state: SimulationState) -> SimulationState:
    """
    LangGraph Node: Business Rules Discovery
    Loads applicable business rules, governance constraints, and rule explanations.
    """
    logger.info("[rules_node] Loading business rules")
    state["current_node"] = "rules"
    context = state.get("context") or {}
    client = RulesClient(
        auth_token=state.get("access_token"),
        enterprise_id=context.get("enterprise_id"),
        domain_ids=context.get("domain_ids"),
        scope_id=context.get("scope_id"),
    )

    try:
        rules_response = await client.get_rules(limit=100)
        rules_list = rules_response.get("rules", [])

        if not isinstance(rules_list, list):
            rules_list = []

        candidate_rules: List[Dict[str, Any]] = [
            rule for rule in rules_list if isinstance(rule, dict)
        ]
        enriched_rules = filter_relevant_rules(candidate_rules, state)

        state["rules"] = enriched_rules
        logger.info(
            "[rules_node] Retained %d of %d rules relevant to selected context",
            len(enriched_rules),
            len(candidate_rules),
        )

    except Exception as exc:
        logger.warning(f"[rules_node] Rules retrieval warning: {exc}")
        state["rules"] = []

    return state
