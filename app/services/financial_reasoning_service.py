import re
from typing import Any, Dict, List


_NAME_KEYS = ("kpi_name", "metric_name", "name", "title", "label", "metric")
_RESTRICTED_TERMS = ("GDV", "HBU", "hurdle", "handover", "construction")


def _records(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, dict):
        for key in ("kpis", "selected_risks", "risks", "items", "results"):
            records = value.get(key)
            if isinstance(records, list):
                return [item for item in records if isinstance(item, dict)]
        return [value] if any(key in value for key in _NAME_KEYS) else []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(_text(item) for item in value)
    return "" if value is None else str(value)


def _name(record: Dict[str, Any]) -> str:
    return str(next(
        (record[key] for key in _NAME_KEYS if record.get(key) not in (None, "")),
        "",
    )).strip()


def _sanitize(value: str, dashboard_semantics: Dict[str, Any]) -> str:
    semantic_text = _text(dashboard_semantics).casefold()
    for term in _RESTRICTED_TERMS:
        if not re.search(rf"\b{re.escape(term)}\b", semantic_text):
            value = re.sub(
                rf"\b{re.escape(term)}\b",
                " ",
                value,
                flags=re.IGNORECASE,
            )
    return " ".join(value.split())


def _dashboard_semantics(state: Dict[str, Any]) -> Dict[str, Any]:
    context = state.get("dashboard_context")
    if isinstance(context, dict):
        semantics = context.get("dashboard_semantics")
        if isinstance(semantics, dict):
            return semantics
    semantics = state.get("dashboard_semantics")
    return semantics if isinstance(semantics, dict) else {}


def _primary_and_supporting_kpis(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    records = []
    primary = state.get("primary_kpi")
    if isinstance(primary, dict):
        records.append(primary)
    supporting = state.get("supporting_kpis")
    if isinstance(supporting, list):
        records.extend(item for item in supporting if isinstance(item, dict))
    for record in _records(state.get("kpi_insights")):
        if _name(record) and _name(record).casefold() not in {
            _name(item).casefold() for item in records
        }:
            records.append(record)
    return records


def _selected_risks(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    records = _records(state.get("selected_risks"))
    if records:
        return records
    for key in ("primary_risk", "secondary_risk"):
        record = state.get(key)
        if isinstance(record, dict):
            records.append(record)
    return records


def _kpi_meaning(
    semantics: Dict[str, Any],
    kpi_name: str,
) -> str:
    target = " ".join(re.findall(r"[a-z0-9]+", kpi_name.casefold()))
    for key in ("kpis", "kpi_definitions", "metrics", "metric_definitions"):
        definitions = semantics.get(key)
        if isinstance(definitions, dict):
            definitions = list(definitions.items())
        elif isinstance(definitions, list):
            definitions = [(None, definition) for definition in definitions]
        if not isinstance(definitions, list):
            continue
        for definition_key, definition in definitions:
            if not isinstance(definition, dict):
                continue
            name = _name(definition) or str(definition_key or "")
            normalized = " ".join(re.findall(r"[a-z0-9]+", name.casefold()))
            if target == normalized:
                return str(
                    definition.get("meaning")
                    or definition.get("description")
                    or definition.get("business_impact")
                    or ""
                ).strip()
    return ""


class FinancialReasoningService:
    """Create cautious financial-impact narratives from supplied evidence."""

    def select_financial_reasoning(self, state: Dict[str, Any]) -> Dict[str, Any]:
        scenario = state.get("scenario")
        scenario = scenario if isinstance(scenario, dict) else {}
        scenario_context = state.get("scenario_context")
        scenario_context = scenario_context if isinstance(scenario_context, dict) else {}
        semantics = _dashboard_semantics(state)
        kpis = _primary_and_supporting_kpis(state)
        risks = _selected_risks(state)

        scenario_parts = [
            str(scenario.get(key) or "").strip()
            for key in ("scenario_type", "change_type", "description")
            if scenario.get(key)
        ]
        if not scenario_parts:
            scenario_parts = [
                str(scenario_context.get(key) or "").strip()
                for key in ("scenario_category", "scenario_objective", "intent_summary")
                if scenario_context.get(key)
            ]
        scenario_description = "; ".join(scenario_parts)

        driver_names = list(dict.fromkeys(
            [name for name in (_name(record) for record in kpis) if name]
            + [
                str(
                    record.get("name")
                    or record.get("title")
                    or record.get("risk")
                    or ""
                ).strip()
                for record in risks
                if record.get("name") or record.get("title") or record.get("risk")
            ]
        ))
        drivers = driver_names or ["No selected KPI or risk evidence"]
        primary_name = _name(kpis[0]) if kpis else ""
        meaning = _kpi_meaning(semantics, primary_name) if primary_name else ""
        entity = str(
            scenario.get("target_entity")
            or state.get("primary_business_entity")
            or scenario_context.get("target_entity")
            or ""
        ).strip()

        evidence = ", ".join(drivers[:4])
        focus = f" for {entity}" if entity else ""
        scenario_clause = (
            f"Scenario context{focus}: {scenario_description}."
            if scenario_description
            else f"Scenario context{focus} is not sufficiently specified."
        )
        meaning_clause = f" Dashboard metadata describes {primary_name} as {meaning}." if meaning else ""
        impact = (
            f"Potential financial effects should be assessed against {evidence}."
            if driver_names
            else "No financial effect can be established from the selected evidence."
        )
        derivation = (
            f"{scenario_clause}{meaning_clause} {impact} "
            "The available evidence does not establish a quantified causal estimate."
        )
        summary = (
            f"Assess the financial implications of the scenario using {evidence}."
            if driver_names
            else "Financial implications remain unclassified until relevant KPI or risk evidence is available."
        )
        formula = (
            "No calculation is available without a validated baseline and an explicit financial relationship."
        )

        return {
            "model_type": "EVIDENCE_BASED_FINANCIAL_IMPACT",
            "primary_drivers": [_sanitize(item, semantics) for item in drivers[:5]],
            "formula": _sanitize(formula, semantics),
            "derivation": _sanitize(derivation, semantics),
            "executive_summary": _sanitize(summary, semantics),
            "assumptions": [
                "No causal or quantitative financial relationship is assumed without supporting evidence.",
                "Dashboard semantic metadata is authoritative for KPI meaning.",
            ],
            "investment_impact": _sanitize(impact, semantics),
        }
