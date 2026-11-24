import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.financial_model_service import classify_kpi
from app.services.root_cause_analysis_service import RootCauseAnalysisService


_KPI_NAME_KEYS = ("kpi_name", "metric_name", "name", "title", "label", "metric")
_KPI_VALUE_KEYS = ("kpi_value", "value", "current_value", "metric_value", "score", "amount", "count")
_CONFIDENCE_KEYS = ("confidence_score", "confidence")
_KPI_COLLECTIONS = ("kpis", "recent_kpis", "insights", "items", "data", "results")
_STOP_WORDS = {
    "about", "after", "again", "against", "could", "does", "during", "from",
    "have", "into", "might", "more", "most", "should", "than", "that", "their",
    "there", "these", "this", "through", "under", "what", "when", "where",
    "which", "while", "with", "would", "will", "into", "risk", "scenario",
    "change", "increases", "increase", "decreases", "decrease", "declines",
    "decline", "drops", "drop", "falls", "fall", "rises", "rise",
}
_GRAPH_SUMMARY_KEYS = ("name", "entity_name", "node_id", "relationship_type")


def _records(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in _KPI_COLLECTIONS:
        records = payload.get(key)
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
    raw = payload.get("raw")
    summary = raw.get("kpi_summary") if isinstance(raw, dict) else None
    recent = summary.get("recent_kpis") if isinstance(summary, dict) else None
    return [item for item in recent if isinstance(item, dict)] if isinstance(recent, list) else []


def _scenario_text(scenario: Any) -> str:
    if isinstance(scenario, dict):
        return " ".join(
            str(scenario[key])
            for key in (
                "query",
                "description",
                "change_type",
                "change_description",
                "scenario_type",
                "scenario_category",
                "category",
                "domain",
                "target_entity",
                "direction",
            )
            if scenario.get(key) not in (None, "")
        )
    return str(scenario or "")


def classify_scenario(
    scenario: Any,
    kpi_records: Optional[List[Dict[str, Any]]] = None,
    scenario_context: Any = None,
    dashboard_semantics: Any = None,
    dashboard_context: Any = None,
) -> str:
    """Resolve only declared scenario categories; do not infer them from prose."""
    sources = (
        (scenario_context, ("scenario_category", "category", "intent_type")),
        (scenario, ("scenario_category", "category", "risk_category")),
        (dashboard_semantics, ("scenario_category", "intent_type")),
    )
    for source, keys in sources:
        if not isinstance(source, dict):
            continue
        category = next((source.get(key) for key in keys if source.get(key)), None)
        if isinstance(category, dict):
            category = category.get("category") or category.get("scenario_category")
        if isinstance(category, str) and category.strip():
            normalized = category.strip().upper().replace("-", "_").replace(" ", "_")
            if normalized not in {"UNCLASSIFIED", "UNKNOWN", "UNSPECIFIED"}:
                return normalized

    capabilities = None
    for source in (dashboard_semantics, dashboard_context):
        if isinstance(source, dict):
            capabilities = (
                source.get("capabilities")
                or source.get("dashboard_capabilities")
            )
            if isinstance(capabilities, dict):
                break
    scenario_type = (
        scenario.get("scenario_type")
        if isinstance(scenario, dict)
        else None
    )
    intent_map = capabilities.get("scenario_intent_map") if isinstance(capabilities, dict) else None
    if isinstance(intent_map, dict) and scenario_type:
        normalized_type = str(scenario_type).strip().casefold().replace("-", "_").replace(" ", "_")
        for key, mapping in intent_map.items():
            if str(key).strip().casefold().replace("-", "_").replace(" ", "_") != normalized_type:
                continue
            if isinstance(mapping, dict):
                mapped = mapping.get("scenario_category") or mapping.get("category")
                if isinstance(mapped, str) and mapped.strip():
                    return mapped.strip().upper().replace("-", "_").replace(" ", "_")
            elif isinstance(mapping, str) and mapping.strip():
                return mapping.strip().upper().replace("-", "_").replace(" ", "_")

    if kpi_records:
        for record in kpi_records:
            category = record.get("scenario_category") or record.get("category")
            if isinstance(category, str) and category.strip():
                return category.strip().upper().replace("-", "_").replace(" ", "_")
    return "UNCLASSIFIED"


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(_text(item) for item in value)
    return "" if value is None else str(value)


def _brief(value: Any, words: int = 18) -> str:
    parts = " ".join(_text(value).split()).split()
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def _filter_unlisted_domain_terms(value: Any, dashboard_semantics: Dict[str, Any]) -> Any:
    semantic_text = str(dashboard_semantics).casefold()
    if isinstance(value, dict):
        return {
            key: _filter_unlisted_domain_terms(item, dashboard_semantics)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _filter_unlisted_domain_terms(item, dashboard_semantics)
            for item in value
        ]
    if not isinstance(value, str):
        return value
    for term in ("GDV", "HBU", "hurdle", "handover", "construction"):
        if not re.search(rf"\b{re.escape(term)}\b", semantic_text):
            value = re.sub(
                rf"\b{re.escape(term)}\b",
                " ",
                value,
                flags=re.IGNORECASE,
            )
    return " ".join(value.split())


def _confidence(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if 1 < number <= 100:
        number /= 100
    return min(max(number, 0.0), 1.0)


def _tokens(value: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[a-zA-Z0-9]+", value)
        if len(token) > 2 and token.casefold() not in _STOP_WORDS
    }


def _kpi_name(record: Dict[str, Any]) -> str:
    return str(next(
        (record[key] for key in _KPI_NAME_KEYS if record.get(key) not in (None, "")),
        "Business indicator",
    ))


def _kpi_reasoning(record: Dict[str, Any]) -> str:
    return _text(
        record.get("reasoning")
        or record.get("explanation")
        or record.get("rationale")
        or record.get("description")
    )


def _kpi_value(record: Dict[str, Any]) -> Any:
    return next(
        (record[key] for key in _KPI_VALUE_KEYS if record.get(key) not in (None, "")),
        None,
    )


def _kpi_relevance(
    record: Dict[str, Any],
    scenario_terms: set[str],
    matched_records: List[Dict[str, Any]],
    scenario_category: Optional[str] = None,
    matched_entities: Any = None,
) -> Tuple[float, float, float, float, float]:
    label = _kpi_name(record)
    reasoning = _kpi_reasoning(record)
    kpi_terms = _tokens(f"{label} {reasoning}")
    overlap = len(scenario_terms.intersection(kpi_terms))
    category_aliases = {
        "CUSTOMER_EXPERIENCE": "CUSTOMER",
    }
    category = str(scenario_category or "").upper()
    category_match = float(
        bool(category)
        and classify_kpi(record)
        == category_aliases.get(category, category)
    )
    entity_values = []
    if isinstance(record.get("entities"), list):
        entity_values.extend(_text(record["entities"]).split())
    for key in (
        "entity",
        "entity_name",
        "customer",
        "account",
        "vendor",
        "project",
        "site",
        "plant",
        "department",
        "business_unit",
    ):
        if record.get(key) not in (None, ""):
            entity_values.append(_text(record[key]))
    entity_terms = _tokens(" ".join(entity_values))
    matched_entity_values = []
    if isinstance(matched_entities, dict):
        for key in ("target_entity", "matched_entities", "entities"):
            value = matched_entities.get(key)
            if value not in (None, ""):
                matched_entity_values.append(_text(value))
    elif isinstance(matched_entities, (list, tuple, set)):
        matched_entity_values.extend(_text(item) for item in matched_entities)
    elif matched_entities not in (None, ""):
        matched_entity_values.append(_text(matched_entities))
    for matched_record in matched_records[:250]:
        if not isinstance(matched_record, dict):
            continue
        for key in (
            "entity",
            "entity_name",
            "customer",
            "account",
            "vendor",
            "project",
            "site",
            "plant",
            "department",
            "business_unit",
        ):
            if matched_record.get(key) not in (None, ""):
                matched_entity_values.append(_text(matched_record[key]))
    matched_entity_terms = _tokens(" ".join(matched_entity_values))
    entity_match = float(
        bool(entity_terms.intersection(matched_entity_terms))
        or bool(kpi_terms.intersection(matched_entity_terms))
    )
    dashboard_terms = _tokens(" ".join(
        _text(item) for item in matched_records[:250]
    ))
    dashboard_support = float(bool(kpi_terms.intersection(dashboard_terms)))
    overlap_score = min(overlap / 2, 1.0)
    relevance = (
        category_match * 0.35
        + overlap_score * 0.35
        + entity_match * 0.2
        + dashboard_support * 0.1
    )
    return relevance, category_match, overlap_score, entity_match, dashboard_support


def score_kpi_relevance(
    *,
    scenario: Any,
    record: Dict[str, Any],
    matched_records: Optional[List[Dict[str, Any]]] = None,
    dashboard_context: Any = None,
    business_context: Any = None,
    scenario_category: Optional[str] = None,
    matched_entities: Any = None,
) -> Dict[str, Any]:
    """Score scenario-to-KPI relevance separately from evidence confidence."""
    scenario_text = _scenario_text(scenario)
    category = str(scenario_category or classify_scenario(scenario)).upper()
    matched = matched_records if isinstance(matched_records, list) else []
    context_text = " ".join(
        _text(value)
        for value in (dashboard_context, business_context)
        if value not in (None, "")
    )
    scenario_terms = _tokens(scenario_text)
    kpi_terms = _tokens(f"{_kpi_name(record)} {_kpi_reasoning(record)}")
    overlap = len(scenario_terms.intersection(kpi_terms))
    context_support = float(bool(kpi_terms.intersection(_tokens(context_text))))
    base_score, category_match, _, entity_support, dashboard_support = _kpi_relevance(
        record,
        scenario_terms,
        matched,
        category,
        matched_entities,
    )
    score = min(1.0, base_score + context_support * 0.1)
    reasons = []
    if category_match:
        reasons.append(f"{classify_kpi(record).title()} KPI aligns with the {category.casefold()} scenario")
    if overlap:
        reasons.append(f"{overlap} scenario term{'s' if overlap != 1 else ''} match the KPI evidence")
    if entity_support:
        reasons.append("matched entity evidence supports the indicator")
    if dashboard_support:
        reasons.append("matched dashboard evidence supports the indicator")
    if context_support:
        reasons.append("business context supports the link")
    return {
        "score": round(score, 3),
        "rationale": "; ".join(reasons) or "No direct scenario, entity, or context link was found",
    }


def build_business_causal_chain(
    scenario: Any,
    scenario_category: str,
    primary_business_entity: str = "",
    primary_kpi: Any = None,
    supporting_kpis: Any = None,
    selected_risks: Any = None,
    dashboard_semantics: Any = None,
    root_causes: Any = None,
) -> List[str]:
    """Build a cautious evidence path from the selected dashboard context."""
    metadata = dashboard_semantics if isinstance(dashboard_semantics, dict) else {}
    scenario_label = (
        _brief(scenario.get("description") or scenario.get("scenario_type") or scenario, words=12)
        if isinstance(scenario, dict)
        else _brief(scenario, words=12)
    )
    entity = primary_business_entity.strip()
    primary_name = _kpi_name(primary_kpi) if isinstance(primary_kpi, dict) else ""
    root_cause = ""
    if isinstance(root_causes, list) and root_causes and isinstance(root_causes[0], dict):
        root_cause = str(root_causes[0].get("root_cause") or "")
    risks = selected_risks if isinstance(selected_risks, list) else []
    risk_names = [
        _brief(
            risk.get("name") or risk.get("title") or risk.get("risk") or risk.get("description"),
            words=10,
        )
        for risk in risks
        if isinstance(risk, dict)
    ]
    kpi_names = [
        _kpi_name(item)
        for item in (supporting_kpis if isinstance(supporting_kpis, list) else [])
        if isinstance(item, dict)
    ]
    path = [
        item
        for item in (
            f"{entity}: {scenario_label}" if entity and scenario_label else scenario_label,
            f"Selected indicator: {primary_name}" if primary_name else "",
            f"Evidence-based contributor: {root_cause}" if root_cause else "",
            *[f"Related indicator: {name}" for name in kpi_names[:2] if name],
            *[f"Selected risk: {name}" for name in risk_names[:2] if name],
        )
        if item
    ]
    if not path:
        path.append("Insufficient scenario-linked evidence to establish an impact path.")
    declared_path = metadata.get("causal_path")
    if isinstance(declared_path, list) and declared_path:
        return [_brief(item, words=18) for item in declared_path if item not in (None, "")]
    return path[:6]


def _graph_context(
    graph_summary: Any,
    dependency_paths: Any,
    related_entities: Any,
) -> Tuple[bool, List[str]]:
    summary = graph_summary if isinstance(graph_summary, dict) else {}
    paths = dependency_paths if isinstance(dependency_paths, list) else []
    entities = related_entities if isinstance(related_entities, list) else []
    node_count = summary.get("total_nodes", 0)
    edge_count = summary.get("total_edges", 0)
    has_graph_data = (
        isinstance(node_count, (int, float))
        and isinstance(edge_count, (int, float))
        and (node_count > 0 or edge_count > 0)
    )
    graph_exists = bool(
        has_graph_data
        and summary.get("graph_exists", True)
    )
    if not graph_exists:
        return False, []
    evidence = []
    for path in paths[:2]:
        if not isinstance(path, dict):
            continue
        names = path.get("entities", [])
        relationships = path.get("relationships", [])
        if not isinstance(names, list) or not names:
            continue
        chain = str(names[0])
        for index, name in enumerate(names[1:]):
            edge = (
                f" -[{relationships[index]}]-> "
                if isinstance(relationships, list) and index < len(relationships)
                else " -> "
            )
            chain += edge + str(name)
        evidence.append(_brief(chain, words=22))
    if not evidence:
        names = [
            str(next((item[key] for key in _GRAPH_SUMMARY_KEYS if item.get(key)), ""))
            for item in entities[:3]
            if isinstance(item, dict)
        ]
        if names:
            evidence.append("Related entities: " + ", ".join(names))
    return True, evidence


class CausalReasoningService:
    """Derive domain-agnostic, evidence-linked business impact paths."""

    def analyze(
        self,
        *,
        scenario: Any,
        dashboard_data: Any,
        matched_dashboard_records: Any,
        kpi_insights: Any,
        actions: Any,
        rules: Any,
        impact_result: Any,
        graph_summary: Any = None,
        dependency_paths: Any = None,
        related_entities: Any = None,
        matched_entities: Any = None,
        primary_kpi: Any = None,
        supporting_kpis: Any = None,
        selected_risks: Any = None,
        scenario_context: Any = None,
        dashboard_context: Any = None,
        dashboard_semantics: Any = None,
    ) -> Dict[str, Any]:
        scenario_text = _scenario_text(scenario)
        matched = matched_dashboard_records if isinstance(matched_dashboard_records, list) else []
        if not matched:
            matched = _records(dashboard_data)
        all_kpis = _records(kpi_insights)
        if not isinstance(dashboard_context, dict):
            dashboard_context = {}
        if not isinstance(dashboard_semantics, dict):
            dashboard_semantics = dashboard_context.get("dashboard_semantics")
        if not isinstance(dashboard_semantics, dict):
            dashboard_semantics = {}
        if not isinstance(scenario_context, dict):
            scenario_context = {}
        scenario_category = classify_scenario(
            scenario,
            all_kpis,
            scenario_context=scenario_context,
            dashboard_semantics=dashboard_semantics,
            dashboard_context=dashboard_context,
        )
        selected_kpis = [
            item
            for item in [primary_kpi]
            + (supporting_kpis if isinstance(supporting_kpis, list) else [])
            if isinstance(item, dict) and _kpi_name(item) != "KPI"
        ]
        kpis = selected_kpis
        primary = kpis[0] if kpis else {}
        category = str(
            (primary.get("scenario_category") or primary.get("category"))
            if primary and (primary.get("scenario_category") or primary.get("category"))
            else scenario_category
        )
        primary_name = _kpi_name(primary) if primary else ""
        matched_entity_values = (
            matched_entities.get("target_entity", "")
            if isinstance(matched_entities, dict)
            else ""
        )
        if not matched_entity_values and isinstance(scenario, dict):
            matched_entity_values = scenario.get("target_entity", "")
        graph_available, graph_evidence = _graph_context(
            graph_summary,
            dependency_paths,
            related_entities,
        )

        impact = impact_result if isinstance(impact_result, dict) else {}
        root_causes = RootCauseAnalysisService().analyze(
            scenario=scenario,
            dashboard_data=dashboard_data,
            matched_dashboard_records=matched,
            kpi_insights=kpi_insights,
            rules=rules,
            actions=actions,
            impact_result=impact,
            scenario_category=scenario_category,
            primary_kpi=primary,
            supporting_kpis=kpis[1:],
            selected_risks=selected_risks,
            dashboard_context=dashboard_context,
            dashboard_semantics=dashboard_semantics,
            scenario_context=scenario_context,
        )
        path = build_business_causal_chain(
            scenario,
            scenario_category,
            str(matched_entity_values or ""),
            primary_kpi=primary,
            supporting_kpis=kpis[1:],
            selected_risks=selected_risks,
            dashboard_semantics=dashboard_semantics,
            root_causes=root_causes,
        )
        if graph_evidence and root_causes:
            root_causes[0]["evidence"] = list(dict.fromkeys(
                [*root_causes[0].get("evidence", []), *graph_evidence]
            ))[:3]

        reasoning = _kpi_reasoning(primary) if primary else ""
        value = _kpi_value(primary) if primary else None
        confidence = _confidence(next(
            (primary[key] for key in _CONFIDENCE_KEYS if primary.get(key) is not None),
            None,
        )) if primary else None
        causal_basis = []
        if primary:
            relevance = score_kpi_relevance(
                scenario=scenario,
                record=primary,
                matched_records=matched,
                dashboard_context=dashboard_context,
                business_context=dashboard_semantics,
                scenario_category=scenario_category,
                matched_entities=matched_entities,
            )
            causal_basis.append({
                "kpi": primary_name,
                "category": category,
                "current_value": value,
                "reasoning": _brief(reasoning, words=24),
                "confidence": confidence,
                "relevance_score": relevance["score"],
                "relevance_rationale": relevance["rationale"],
            })
        for record in kpis[1:5]:
            relevance = score_kpi_relevance(
                scenario=scenario,
                record=record,
                matched_records=matched,
                dashboard_context=dashboard_context,
                business_context=dashboard_semantics,
                scenario_category=scenario_category,
                matched_entities=matched_entities,
            )
            causal_basis.append({
                "kpi": _kpi_name(record),
                "category": classify_kpi(record),
                "current_value": _kpi_value(record),
                "reasoning": _brief(_kpi_reasoning(record), words=24),
                "confidence": _confidence(next(
                    (record[key] for key in _CONFIDENCE_KEYS if record.get(key) is not None),
                    None,
                )),
                "relevance_score": relevance["score"],
                "relevance_rationale": relevance["rationale"],
            })
        if graph_evidence:
            causal_basis.append({"source": "Knowledge Graph", "evidence": graph_evidence})

        return _filter_unlisted_domain_terms({
            "scenario_change": _brief(scenario_text, words=30),
            "scenario_category": scenario_category.casefold(),
            "kpi_relevance": {
                _kpi_name(record): score_kpi_relevance(
                    scenario=scenario,
                    record=record,
                    matched_records=matched,
                    dashboard_context=dashboard_context,
                    business_context=dashboard_semantics,
                    scenario_category=scenario_category,
                    matched_entities=matched_entities,
                )
                for record in kpis[:5]
            },
            "primary_kpi": primary_name or None,
            "primary_kpi_category": category,
            "causal_chain": path,
            "primary_impact_path": " → ".join(path),
            "business_consequence": (
                root_causes[0]["business_consequence"]
                if root_causes
                else "Potential business consequences require validation against dashboard evidence."
            ),
            "causal_basis": causal_basis,
            "graph_evidence": graph_evidence,
            "graph_available": graph_available,
            "confidence": confidence,
            "confidence_reason": (
                None
                if confidence is not None
                else "No source KPI confidence data was provided."
            ),
            "current_enterprise_problems": [
                {
                    "name": _brief(item.get("name"), words=12),
                    "value": _brief(item.get("formatted_amount"), words=8),
                }
                for item in (
                    impact.get("financial_model", {}).get("current_exposure", {}).get("items", [])
                    if isinstance(impact.get("financial_model"), dict)
                    and isinstance(impact.get("financial_model", {}).get("current_exposure"), dict)
                    else []
                )[:3]
                if isinstance(item, dict)
            ],
            "root_cause_analysis": root_causes[:5],
        }, dashboard_semantics)
