import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _scenario_key(value: Any) -> str:
    normalized = str(value or "").strip().casefold().replace("-", " ").replace("_", " ")
    return "_".join(normalized.split())


def get_dashboard_capabilities(dashboard_context: Any) -> Dict[str, Any]:
    if not isinstance(dashboard_context, dict):
        return {}

    semantics = dashboard_context.get("dashboard_semantics")
    sources = [dashboard_context]
    if isinstance(semantics, dict):
        sources.append(semantics)

    for source in sources:
        for key in ("capabilities", "dashboard_capabilities"):
            capabilities = source.get(key)
            if isinstance(capabilities, dict) and capabilities:
                return capabilities
    return {}


def get_scenario_capability_mapping(
    dashboard_context: Any,
    mapping_name: str,
    scenario_type: Any,
) -> Any:
    scenario_key = _scenario_key(scenario_type)
    mapping = get_dashboard_capabilities(dashboard_context).get(mapping_name)
    if not scenario_key or not isinstance(mapping, dict):
        return None

    for key, value in mapping.items():
        if _scenario_key(key) == scenario_key:
            return value
    return None


def _identifier(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    identifier = _scenario_key(value).upper()
    if identifier in {"", "UNKNOWN", "UNSPECIFIED", "UNCLASSIFIED"}:
        return "UNCLASSIFIED"
    return identifier


def _first_identifier(*values: Any) -> str:
    for value in values:
        identifier = _identifier(value)
        if identifier and identifier != "UNCLASSIFIED":
            return identifier
    return "UNCLASSIFIED"


def _list_value(value: Any) -> List[Any]:
    if isinstance(value, (list, tuple)):
        return [item for item in value if item not in (None, "")]
    if value in (None, ""):
        return []
    return [value]


def _intent_mapping(mapping: Any) -> Dict[str, Any]:
    if isinstance(mapping, dict):
        return mapping
    if isinstance(mapping, str) and mapping.strip():
        return {"scenario_category": mapping, "intent_type": mapping}
    return {}


class ScenarioIntentService:
    """Build scenario context from parsed fields and declared capabilities."""

    def classify(self, state: Dict[str, Any]) -> Dict[str, Any]:
        query = str(state.get("query") or "")
        scenario = state.get("scenario")
        if not isinstance(scenario, dict):
            scenario = {}
        existing_context = state.get("scenario_context")
        if not isinstance(existing_context, dict):
            existing_context = {}
        existing_semantics = state.get("scenario_semantics")
        if not isinstance(existing_semantics, dict):
            existing_semantics = existing_context.get("scenario_semantics")
        if not isinstance(existing_semantics, dict):
            existing_semantics = {}

        dashboard_context = state.get("dashboard_context")
        if not isinstance(dashboard_context, dict):
            dashboard_context = {}
        scenario_type = scenario.get("scenario_type") or existing_context.get("scenario_type")
        mapping = get_scenario_capability_mapping(
            dashboard_context,
            "scenario_intent_map",
            scenario_type,
        )
        mapped_intent = _intent_mapping(mapping)

        scenario_category = _first_identifier(
            existing_context.get("scenario_category"),
            scenario.get("scenario_category"),
            mapped_intent.get("scenario_category"),
            mapped_intent.get("category"),
        )
        intent_type = _first_identifier(
            existing_semantics.get("intent_type"),
            existing_context.get("intent_type"),
            scenario.get("intent_type"),
            mapped_intent.get("intent_type"),
            mapped_intent.get("intent"),
            scenario_category,
        )
        decision_type = _first_identifier(
            existing_context.get("decision_type"),
            scenario.get("decision_type"),
            mapped_intent.get("decision_type"),
            scenario_category,
        )
        themes = _list_value(
            existing_semantics.get("themes")
            or existing_context.get("themes")
            or scenario.get("themes")
            or mapped_intent.get("themes")
        )
        target_entity = (
            scenario.get("target_entity")
            or existing_context.get("target_entity")
            or state.get("primary_business_entity")
            or ""
        )
        decision_horizon = (
            scenario.get("time_horizon")
            or existing_context.get("decision_horizon")
            or "UNCLASSIFIED"
        )
        capital_allocation = existing_context.get(
            "is_capital_allocation",
            scenario.get("is_capital_allocation", False),
        )

        scenario_semantics = dict(existing_semantics)
        scenario_semantics.update({
            "themes": themes,
            "intent_summary": (
                existing_semantics.get("intent_summary")
                or scenario.get("description")
                or query.strip()
            ),
            "intent_type": intent_type,
        })

        result = dict(existing_context)
        result.update(scenario)
        result.update({
            "scenario_category": scenario_category,
            "scenario_objective": (
                scenario.get("objective")
                or scenario.get("description")
                or query.strip()
            ),
            "decision_type": decision_type,
            "decision_horizon": decision_horizon,
            "is_capital_allocation": (
                capital_allocation if isinstance(capital_allocation, bool) else False
            ),
            "target_entity": target_entity,
            "query_summary": query.strip(),
            "scenario_semantics": scenario_semantics,
        })

        logger.info(
            "[ScenarioIntentService] category=%s scenario_type=%s",
            scenario_category,
            scenario_type or "UNCLASSIFIED",
        )
        return result
