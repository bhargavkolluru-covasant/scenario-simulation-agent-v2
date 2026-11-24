import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.services.llm_gateway import LLMGateway
from app.services.scenario_intent_service import get_scenario_capability_mapping
from app.state.simulation_state import SimulationState

logger = logging.getLogger(__name__)


class SimulationStrategy(str, Enum):
    """Strategies selected through explicit scenario capabilities."""
    PORTFOLIO_OPTIMIZATION = "PORTFOLIO_OPTIMIZATION"
    PROJECT_DELIVERY_SIMULATION = "PROJECT_DELIVERY_SIMULATION"
    CUSTOMER_EXPERIENCE_SIMULATION = "CUSTOMER_EXPERIENCE_SIMULATION"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    FINANCIAL_IMPACT = "FINANCIAL_IMPACT"
    MARKET_RISK = "MARKET_RISK"
    DEMAND_GROWTH = "DEMAND_GROWTH"
    CAPACITY_PLANNING = "CAPACITY_PLANNING"
    RULE_BASED = "RULE_BASED"
    HYBRID = "HYBRID"
    UNCLASSIFIED = "UNCLASSIFIED"


class StrategyDecision(BaseModel):
    strategy: SimulationStrategy
    rationale: Optional[str] = Field(default="", description="Reasoning for selecting this simulation strategy")


def _as_strategy(value: Any) -> SimulationStrategy:
    if isinstance(value, dict):
        value = value.get("strategy") or value.get("simulation_strategy")
    if isinstance(value, SimulationStrategy):
        return value
    if not isinstance(value, str) or not value.strip():
        return SimulationStrategy.UNCLASSIFIED
    try:
        return SimulationStrategy(value.strip().upper().replace(" ", "_"))
    except ValueError:
        return SimulationStrategy.UNCLASSIFIED


def _scenario_type(scenario: Dict[str, Any], scenario_context: Dict[str, Any]) -> str:
    return str(
        scenario.get("scenario_type")
        or scenario_context.get("scenario_type")
        or ""
    )


def _mapping_methodology(mapping: Any) -> List[str]:
    if not isinstance(mapping, dict):
        return []
    methodology = mapping.get("methodology")
    if isinstance(methodology, str):
        return [methodology] if methodology else []
    if isinstance(methodology, (list, tuple)):
        return [str(item) for item in methodology if item not in (None, "")]
    return []


def determine_strategy(
    scenario: Dict[str, Any],
    scenario_context: Optional[Dict[str, Any]] = None,
    dashboard_context: Optional[Dict[str, Any]] = None,
    scenario_semantics: Optional[Dict[str, Any]] = None,
) -> SimulationStrategy:
    """Resolve an explicit strategy or an exact scenario capability mapping."""
    scenario = scenario if isinstance(scenario, dict) else {}
    scenario_context = scenario_context if isinstance(scenario_context, dict) else {}
    scenario_semantics = scenario_semantics if isinstance(scenario_semantics, dict) else {}

    for source in (scenario_context, scenario_semantics, scenario):
        for key in ("simulation_strategy", "strategy", "strategy_type"):
            if source.get(key) not in (None, ""):
                strategy = _as_strategy(source[key])
                if strategy != SimulationStrategy.UNCLASSIFIED:
                    return strategy

    scenario_type = _scenario_type(scenario, scenario_context)
    mapping = get_scenario_capability_mapping(
        scenario_context,
        "scenario_strategy_map",
        scenario_type,
    )
    if mapping is None:
        mapping = get_scenario_capability_mapping(
            dashboard_context,
            "scenario_strategy_map",
            scenario_type,
        )
    return _as_strategy(mapping)


async def strategy_selector_node(
    state: SimulationState,
    llm_service: Optional[LLMGateway] = None,
) -> SimulationState:
    """Select a strategy from parsed scenario and declared dashboard capabilities."""
    del llm_service
    logger.info("[strategy_selector_node] Selecting simulation execution strategy")
    state["current_node"] = "strategy_selector"

    scenario = state.get("scenario")
    if not isinstance(scenario, dict):
        scenario = {}
    scenario_context = state.get("scenario_context")
    if not isinstance(scenario_context, dict):
        scenario_context = {}
    dashboard_context = state.get("dashboard_context")
    if not isinstance(dashboard_context, dict):
        dashboard_context = {}
    scenario_semantics = state.get("scenario_semantics")
    if not isinstance(scenario_semantics, dict):
        scenario_semantics = {}

    scenario_type = _scenario_type(scenario, scenario_context)
    mapping = get_scenario_capability_mapping(
        scenario_context,
        "scenario_strategy_map",
        scenario_type,
    )
    if mapping is None:
        mapping = get_scenario_capability_mapping(
            dashboard_context,
            "scenario_strategy_map",
            scenario_type,
        )
    strategy = determine_strategy(
        scenario=scenario,
        scenario_context=scenario_context,
        dashboard_context=dashboard_context,
        scenario_semantics=scenario_semantics,
    )
    dashboard_category = str(dashboard_context.get("category") or "")
    scenario_category = str(scenario_context.get("scenario_category") or "")
    methodology = _mapping_methodology(mapping)

    state["simulation_strategy"] = strategy.value
    state["simulation_strategy_context"] = {
        "strategy": strategy.value,
        "methodology": methodology,
        "dashboard_category": dashboard_category,
        "scenario_category": scenario_category,
        "scenario_type": scenario_type or "UNCLASSIFIED",
    }
    logger.info(
        "[strategy_selector_node] Strategy assigned: '%s'",
        strategy.value,
    )
    return state


class StrategySelectorNode:
    """Class wrapper for backward compatibility."""

    def __init__(self, llm_service: Optional[LLMGateway] = None):
        self.llm_service = llm_service

    async def execute(self, state: SimulationState) -> SimulationState:
        return await strategy_selector_node(state, llm_service=self.llm_service)
