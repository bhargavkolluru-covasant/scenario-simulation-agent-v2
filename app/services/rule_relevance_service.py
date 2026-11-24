import re
from typing import Any, Dict, Iterable, List, Set


_DASHBOARD_FIELDS = (
    "dashboard_category",
    "dashboard_categories",
    "dashboard_type",
    "dashboard_types",
    "dashboard_id",
    "dashboard_ids",
    "business_domain",
    "domain",
    "category",
)
_SCENARIO_FIELDS = (
    "scenario_category",
    "scenario_categories",
    "scenario_type",
    "scenario_types",
    "intent_type",
    "intent_types",
)
_KPI_FIELDS = (
    "kpi",
    "kpi_name",
    "kpi_names",
    "kpis",
    "metric",
    "metric_name",
    "metric_names",
    "metrics",
    "indicator",
    "indicators",
)
_RISK_FIELDS = (
    "risk",
    "risk_name",
    "risk_names",
    "risks",
    "risk_category",
    "risk_categories",
)
_SEMANTIC_FIELDS = (
    "rule_groups",
    "risk_groups",
    "kpi_groups",
    "themes",
    "relevant_terms",
    "business_terms",
    "rule_aliases",
)
_SELECTED_RULE_FIELDS = (
    "selected_rule_ids",
    "applicable_rule_ids",
    "allowed_rule_ids",
    "rule_ids",
    "selected_rules",
    "applicable_rules",
    "rules",
)
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "or", "the", "to", "with", "what", "when",
    "where", "which", "who", "why", "will", "would", "may", "might", "can",
    "could", "should", "must", "if", "than", "then", "this", "that", "these",
    "those", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "risk", "rule", "policy", "business", "flag", "high", "medium", "low",
    "critical", "alert", "threshold", "months", "month", "quarter", "next",
    "increase", "decrease", "impact", "scenario", "category", "domain",
}
_DEFINITION_FIELDS = (
    "meaning",
    "description",
    "aliases",
    "related_terms",
    "root_cause",
    "likely_cause",
    "business_impact",
    "business_consequence",
)


def _strings(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        result = []
        for key in (
            "name",
            "title",
            "id",
            "rule_id",
            "rule_name",
            "risk_name",
            "kpi_name",
            "metric_name",
            "value",
            "label",
            "aliases",
            "related_terms",
        ):
            result.extend(_strings(value.get(key)))
        return result
    if isinstance(value, (list, tuple, set)):
        return [
            text
            for item in value
            for text in _strings(item)
        ]
    return []


def _tokens(values: Iterable[str]) -> Set[str]:
    tokens = set()
    for value in values:
        for token in re.findall(r"[a-z0-9]+", value.casefold()):
            if len(token) <= 2 or token in _STOP_WORDS:
                continue
            tokens.add(token[:-1] if token.endswith("s") and len(token) > 4 else token)
    return tokens


def _normalized(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _sources(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _selected_records(state: Dict[str, Any], key: str, fallback_keys: tuple) -> List[Dict[str, Any]]:
    value = state.get(key)
    records = _sources(value)
    if records:
        return records
    return [
        state[field]
        for field in fallback_keys
        if isinstance(state.get(field), dict)
    ]


def _dashboard_semantics(state: Dict[str, Any]) -> Dict[str, Any]:
    context = state.get("dashboard_context")
    if isinstance(context, dict) and isinstance(context.get("dashboard_semantics"), dict):
        return context["dashboard_semantics"]
    semantics = state.get("dashboard_semantics")
    return semantics if isinstance(semantics, dict) else {}


def _semantic_kpi_values(
    semantics: Dict[str, Any],
    selected_kpis: List[Dict[str, Any]],
) -> List[str]:
    selected_names = {
        _normalized(record.get("name") or record.get("kpi_name"))
        for record in selected_kpis
    }
    values = []
    for key in ("kpis", "kpi_definitions", "metrics", "metric_definitions"):
        definitions = semantics.get(key)
        if isinstance(definitions, dict):
            entries = definitions.items()
        elif isinstance(definitions, list):
            entries = ((None, item) for item in definitions)
        else:
            continue
        for name, definition in entries:
            if not isinstance(definition, dict):
                continue
            definition_name = next(
                (
                    definition[field]
                    for field in ("name", "kpi_name", "metric_name", "title", "label")
                    if definition.get(field)
                ),
                name,
            )
            if _normalized(definition_name) not in selected_names:
                continue
            values.extend(_strings(definition_name))
            for field in _DEFINITION_FIELDS:
                values.extend(_strings(definition.get(field)))
    return values


def _selected_rule_keys(*sources: Dict[str, Any]) -> Set[str]:
    selected = set()
    for source in sources:
        for field in _SELECTED_RULE_FIELDS:
            selected.update(
                _normalized(value)
                for value in _strings(source.get(field))
                if _normalized(value)
            )
    return selected


def _rule_values(rule: Dict[str, Any], fields: tuple) -> List[str]:
    values = []
    sources = [rule]
    for key in ("metadata", "applicability", "scope"):
        nested = rule.get(key)
        if isinstance(nested, dict):
            sources.append(nested)
    for source in sources:
        for field in fields:
            values.extend(_strings(source.get(field)))
    return values


def _rule_identity(rule: Dict[str, Any]) -> Set[str]:
    return {
        _normalized(value)
        for value in _strings(rule.get("rule_id"))
        + _strings(rule.get("id"))
        + _strings(rule.get("name"))
        + _strings(rule.get("title"))
        if _normalized(value)
    }


def _metadata_conflicts(
    rule: Dict[str, Any],
    fields: tuple,
    context_values: List[str],
) -> bool:
    declared = _rule_values(rule, fields)
    if not declared:
        return False
    context = set()
    for value in context_values:
        normalized = _normalized(value)
        if normalized and normalized not in {"unclassified", "unknown", "unspecified"}:
            context.add(normalized)
    if not context:
        return False
    return not any(_normalized(value) in context for value in declared)


def filter_relevant_rules(
    rules: Any,
    state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Keep only enterprise rules applicable to the selected dashboard scenario."""
    records = _sources(rules)
    if not records:
        return []

    dashboard_context = state.get("dashboard_context")
    dashboard_context = dashboard_context if isinstance(dashboard_context, dict) else {}
    semantics = _dashboard_semantics(state)
    scenario_context = state.get("scenario_context")
    scenario_context = scenario_context if isinstance(scenario_context, dict) else {}
    scenario = state.get("scenario")
    scenario = scenario if isinstance(scenario, dict) else {}
    primary_kpis = _selected_records(state, "primary_kpi", ())
    supporting_kpis = _sources(state.get("supporting_kpis"))
    selected_kpis = primary_kpis + supporting_kpis
    risks = _selected_records(
        state,
        "selected_risks",
        ("primary_risk", "secondary_risk"),
    )

    dashboard_values = _strings(dashboard_context.get("category"))
    dashboard_values.extend(_strings(semantics.get("business_domain")))
    dashboard_values.extend(_strings(semantics.get("dashboard_category")))
    dashboard_values.extend(_strings(semantics.get("dashboard_categories")))
    scenario_values = _strings(scenario_context.get("scenario_category"))
    scenario_values.extend(_strings(state.get("scenario_category")))
    scenario_values.extend(_strings(scenario_context.get("scenario_type")))
    scenario_values.extend(_strings(scenario.get("scenario_category")))
    scenario_values.extend(_strings(scenario.get("scenario_type")))
    kpi_values = [
        str(value)
        for record in selected_kpis
        for value in (
            record.get("name") or record.get("kpi_name"),
            record.get("meaning"),
            record.get("description"),
        )
        if value not in (None, "")
    ]
    kpi_values.extend(_semantic_kpi_values(semantics, selected_kpis))
    selected_kpi_names = [
        str(record.get("name") or record.get("kpi_name"))
        for record in selected_kpis
        if record.get("name") or record.get("kpi_name")
    ]
    risk_values = [
        text
        for record in risks
        for text in _strings(record)
    ]
    semantic_values = [
        text
        for field in _SEMANTIC_FIELDS
        for text in _strings(semantics.get(field))
    ]
    scenario_text = _strings(state.get("query"))
    scenario_text.extend(
        str(value)
        for key, value in scenario.items()
        if key not in {"scenario_category", "scenario_type"} and value not in (None, "")
    )
    all_context_values = (
        dashboard_values
        + scenario_values
        + kpi_values
        + risk_values
        + semantic_values
        + scenario_text
    )
    context_tokens = _tokens(all_context_values)
    selected_phrases = {
        _normalized(value)
        for value in selected_kpi_names + risk_values
        if len(_normalized(value)) > 2
    }
    explicit_rule_keys = _selected_rule_keys(semantics, dashboard_context)
    dashboard_id = _normalized(state.get("dashboard_id"))
    if dashboard_id:
        dashboard_values.append(dashboard_id)

    relevant = []
    for rule in records:
        identity = _rule_identity(rule)
        if identity.intersection(explicit_rule_keys):
            relevant.append(rule)
            continue
        if _metadata_conflicts(rule, _DASHBOARD_FIELDS, dashboard_values):
            continue
        if _metadata_conflicts(rule, _SCENARIO_FIELDS, scenario_values):
            continue
        if _metadata_conflicts(rule, _KPI_FIELDS, kpi_values):
            continue
        if _metadata_conflicts(rule, _RISK_FIELDS, risk_values):
            continue
        rule_text = str(rule)
        normalized_rule_text = _normalized(rule_text)
        if any(phrase and phrase in normalized_rule_text for phrase in selected_phrases):
            relevant.append(rule)
            continue
        if len(context_tokens.intersection(_tokens([rule_text]))) >= 2:
            relevant.append(rule)
    return relevant
