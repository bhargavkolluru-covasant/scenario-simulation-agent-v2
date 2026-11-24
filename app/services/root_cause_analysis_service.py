import re
from typing import Any, Dict, List, Optional, Sequence

from app.services.rule_relevance_service import filter_relevant_rules

_NAME_KEYS = ("kpi_name", "metric_name", "name", "title", "label", "metric")
_VALUE_KEYS = ("kpi_value", "value", "current_value", "metric_value", "score", "amount", "count")
_CONFIDENCE_KEYS = ("confidence_score", "confidence")
_RECORD_LIMIT = 250
_EVIDENCE_LIMIT = 3
_CAUSAL_PATTERN = re.compile(
    r"\b(?:due to|because of|driven by|caused by|attributed to|resulting from|linked to|"
    r"lack of|failure to|insufficient|weak|poor|unresolved|below target|not met)\s+([^.;]+)",
    re.IGNORECASE,
)


def _records(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload[:_RECORD_LIMIT] if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("kpis", "recent_kpis", "insights", "items", "data", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value[:_RECORD_LIMIT] if isinstance(item, dict)]
    raw = payload.get("raw")
    summary = raw.get("kpi_summary") if isinstance(raw, dict) else None
    recent = summary.get("recent_kpis") if isinstance(summary, dict) else None
    return [item for item in recent[:_RECORD_LIMIT] if isinstance(item, dict)] if isinstance(recent, list) else []


def _first(record: Dict[str, Any], keys: Sequence[str], default: Any = "") -> Any:
    return next(
        (record[key] for key in keys if record.get(key) not in (None, "")),
        default,
    )


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(_text(item) for item in value)
    return "" if value is None else str(value)


def _brief(value: Any, max_words: int = 22, max_characters: int = 180) -> str:
    text = " ".join(_text(value).split())
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words]) + "…"
    if len(text) > max_characters:
        text = text[:max_characters].rsplit(" ", 1)[0] + "…"
    return text


def _confidence(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if 1 < number <= 100:
        number /= 100
    return min(max(number, 0.0), 1.0)


def _scenario_text(scenario: Any) -> str:
    return _text(scenario)


def _normalized(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _semantic_kpi_definition(
    dashboard_semantics: Dict[str, Any],
    kpi_name: str,
) -> Dict[str, Any]:
    target = _normalized(kpi_name)
    if not target:
        return {}
    for key in ("kpis", "kpi_definitions", "metrics", "metric_definitions"):
        definitions = dashboard_semantics.get(key)
        if isinstance(definitions, dict):
            definitions = list(definitions.items())
        elif isinstance(definitions, list):
            definitions = [(None, definition) for definition in definitions]
        if not isinstance(definitions, list):
            continue
        for definition_key, definition in definitions:
            if not isinstance(definition, dict):
                continue
            name = _first(definition, _NAME_KEYS, definition_key or "")
            if _normalized(name) == target:
                return definition
    return {}


def _semantic_mapping(
    dashboard_semantics: Dict[str, Any],
    mapping_keys: Sequence[str],
    candidates: Sequence[str],
    value_fields: Sequence[str] = (
        "root_cause",
        "business_consequence",
        "mitigation",
        "description",
    ),
) -> str:
    for mapping_key in mapping_keys:
        mapping = dashboard_semantics.get(mapping_key)
        if not isinstance(mapping, dict):
            continue
        normalized_mapping = {
            _normalized(key): value for key, value in mapping.items()
        }
        for candidate in candidates:
            value = normalized_mapping.get(_normalized(candidate))
            if isinstance(value, str) and value.strip():
                return _brief(value, max_words=22, max_characters=180)
            if isinstance(value, dict):
                for field in value_fields:
                    if isinstance(value.get(field), str) and value[field].strip():
                        return _brief(value[field], max_words=22, max_characters=180)
    return ""


def _filter_unlisted_domain_terms(value: Any, dashboard_semantics: Any) -> Any:
    semantic_text = _text(dashboard_semantics).casefold()
    blocked_terms = (
        "gdv",
        "hbu",
        "hurdle",
        "handover",
        "construction",
    )
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
    filtered = value
    for term in blocked_terms:
        if not re.search(rf"\b{re.escape(term)}\b", semantic_text):
            filtered = re.sub(
                rf"\b{re.escape(term)}\b",
                " ",
                filtered,
                flags=re.IGNORECASE,
            )
    return " ".join(filtered.split())


def _cause_name(
    record: Dict[str, Any],
    reasoning: str,
    scenario_category: str,
    primary_kpi_name: str = "",
    dashboard_semantics: Optional[Dict[str, Any]] = None,
) -> str:
    explicit = _first(record, ("root_cause", "potential_root_cause", "cause"))
    if explicit:
        return _brief(explicit, max_words=12, max_characters=90)
    match = _CAUSAL_PATTERN.search(reasoning)
    if match:
        cause = _brief(match.group(1), max_words=12, max_characters=90)
        if cause:
            return cause[0].upper() + cause[1:]
    semantics = dashboard_semantics if isinstance(dashboard_semantics, dict) else {}
    definition = _semantic_kpi_definition(semantics, primary_kpi_name)
    semantic_cause = _first(
        definition,
        ("root_cause", "root_cause_guidance", "likely_cause", "cause"),
    )
    if semantic_cause:
        return _brief(semantic_cause, max_words=12, max_characters=90)
    mapped_cause = _semantic_mapping(
        semantics,
        ("root_cause_map", "root_causes"),
        (primary_kpi_name, scenario_category),
    )
    if mapped_cause:
        return mapped_cause
    if primary_kpi_name:
        return f"Potential contributor affecting {primary_kpi_name} requires validation"
    return "Insufficient evidence to infer a likely driver"


def _narrative_value(
    dashboard_semantics: Dict[str, Any],
    primary_kpi_name: str,
    scenario_category: str,
    fields: Sequence[str],
    mapping_keys: Sequence[str],
    fallback: str,
) -> str:
    definition = _semantic_kpi_definition(dashboard_semantics, primary_kpi_name)
    declared = _first(definition, fields)
    if declared:
        return _brief(declared)
    mapped = _semantic_mapping(
        dashboard_semantics,
        mapping_keys,
        (primary_kpi_name, scenario_category),
        value_fields=fields,
    )
    return mapped or fallback


def _related_source_reasoning(
    name: str,
    reasoning: str,
    matched_records: List[Any],
    rules: List[Any],
    actions: List[Any],
    selected_risks: List[Any],
) -> str:
    key_terms = {
        word.casefold()
        for word in re.findall(r"\w+", f"{name} {reasoning}")
        if len(word) > 3
    }
    relevant = []
    for source in [
        *matched_records[:_RECORD_LIMIT],
        *rules[:_RECORD_LIMIT],
        *actions[:_RECORD_LIMIT],
        *selected_risks[:_RECORD_LIMIT],
    ]:
        if not isinstance(source, dict):
            continue
        content = _text(source)
        source_terms = {
            word.casefold()
            for word in re.findall(r"\w+", content)
            if len(word) > 3
        }
        if key_terms.intersection(source_terms):
            relevant.append(content)
        if len(relevant) >= 3:
            break
    return _brief(" ".join(relevant), max_words=60, max_characters=400)


def _severity_score(
    impact_result: Dict[str, Any],
    record: Dict[str, Any],
) -> Optional[int]:
    severity_by_name = {
        "CRITICAL": 5,
        "HIGH": 4,
        "MEDIUM": 3,
        "MODERATE": 3,
        "LOW": 2,
    }
    record_text = _text(record).casefold()
    score = severity_by_name.get(
        str(
            record.get("severity")
            or record.get("risk_severity")
            or impact_result.get("overall_severity")
            or ""
        ).upper()
    )
    dimensions = impact_result.get("dimensions", [])
    for dimension in dimensions if isinstance(dimensions, list) else []:
        if not isinstance(dimension, dict):
            continue
        if any(word in _text(dimension).casefold() for word in record_text.split() if len(word) > 3):
            dimension_score = severity_by_name.get(
                str(dimension.get("severity", "")).upper()
            )
            if dimension_score is not None:
                score = max(score or dimension_score, dimension_score)
    return score


def _supporting_evidence(
    name: str,
    value: Any,
    reasoning: str,
    scenario: str,
    rules: List[Any],
    actions: List[Any],
    matched_records: List[Any],
    selected_risks: List[Any],
) -> List[str]:
    facts = []
    observation = f"{name}: {value}" if value not in (None, "") else name
    if reasoning:
        observation += f" — {_brief(reasoning, max_words=12, max_characters=90)}"
    facts.append(_brief(observation))

    record_terms = {
        word.casefold()
        for word in re.findall(r"\w+", f"{name} {reasoning}")
        if len(word) > 3
    }
    corroborating: List[str] = []
    for label, sources in (
        ("Dashboard", matched_records),
        ("Rule", rules),
        ("Action", actions),
        ("Risk", selected_risks),
    ):
        for source in sources[:_RECORD_LIMIT]:
            if not isinstance(source, dict):
                continue
            content = _text(source)
            source_terms = {
                word.casefold()
                for word in re.findall(r"\w+", content)
                if len(word) > 3
            }
            if record_terms.intersection(source_terms):
                detail = _first(source, ("name", "title", "action_title", "rule_name", "description"), content)
                corroborating.append(f"{label}: {_brief(detail, max_words=14, max_characters=110)}")
                break
    facts.extend(corroborating[:_EVIDENCE_LIMIT - 1])
    if not corroborating and scenario:
        facts.append(f"Scenario: {_brief(scenario, max_words=14, max_characters=110)}")
    return list(dict.fromkeys(facts))[:_EVIDENCE_LIMIT]


class RootCauseAnalysisService:
    """Generate concise, evidence-linked root-cause hypotheses without domain rules."""

    def analyze(
        self,
        *,
        scenario: Any,
        dashboard_data: Any,
        matched_dashboard_records: Any,
        kpi_insights: Any,
        rules: Any,
        actions: Any,
        impact_result: Any,
        scenario_category: Optional[str] = None,
        primary_kpi: Any = None,
        supporting_kpis: Any = None,
        selected_risks: Any = None,
        dashboard_context: Any = None,
        dashboard_semantics: Any = None,
        scenario_context: Any = None,
    ) -> List[Dict[str, Any]]:
        scenario_text = _scenario_text(scenario)
        if not scenario_category:
            scenario_category = ""
            for source in (scenario_context, scenario):
                if isinstance(source, dict):
                    scenario_category = (
                        source.get("scenario_category")
                        or source.get("decision_type")
                        or ""
                    )
                    if scenario_category:
                        break
        if not scenario_category and isinstance(dashboard_semantics, dict):
            scenario_category = dashboard_semantics.get("scenario_category") or ""
        scenario_category = str(scenario_category).upper()
        if not scenario_category:
            scenario_category = "UNCLASSIFIED"
        if not isinstance(dashboard_semantics, dict):
            dashboard_semantics = {}
        if not isinstance(dashboard_context, dict):
            dashboard_context = {}
        if not isinstance(scenario_context, dict):
            scenario_context = {}
        if not dashboard_semantics:
            dashboard_semantics = dashboard_context.get("dashboard_semantics")
        if not isinstance(dashboard_semantics, dict):
            dashboard_semantics = {}
        impact = impact_result if isinstance(impact_result, dict) else {}
        rule_records = rules if isinstance(rules, list) else []
        action_records = actions if isinstance(actions, list) else []
        risk_records = (
            selected_risks
            if isinstance(selected_risks, list)
            else [selected_risks] if isinstance(selected_risks, dict) else []
        )
        risk_records = [record for record in risk_records if isinstance(record, dict)]
        rule_records = filter_relevant_rules(
            rule_records,
            {
                "dashboard_context": dashboard_context,
                "dashboard_semantics": dashboard_semantics,
                "scenario_context": {
                    **scenario_context,
                    "scenario_category": (
                        scenario_context.get("scenario_category")
                        or scenario_category
                    ),
                },
                "scenario": scenario,
                "query": scenario_text,
                "primary_kpi": primary_kpi,
                "supporting_kpis": supporting_kpis,
                "selected_risks": risk_records,
            },
        )
        matched_records = (
            matched_dashboard_records
            if isinstance(matched_dashboard_records, list)
            else []
        )
        if not matched_records and isinstance(dashboard_data, (list, dict)):
            matched_records = _records(dashboard_data)

        selected_kpis = [
            item
            for item in [primary_kpi]
            + (supporting_kpis if isinstance(supporting_kpis, list) else [])
            if isinstance(item, dict)
        ]
        insight_kpis = _records(kpi_insights)
        kpi_records = selected_kpis + [
            item for item in insight_kpis
            if _normalized(_first(item, _NAME_KEYS))
            not in {_normalized(_first(selected, _NAME_KEYS)) for selected in selected_kpis}
        ]
        candidates: List[Dict[str, Any]] = []
        seen = set()
        for record in kpi_records:
            name = _brief(_first(record, _NAME_KEYS, "Business indicator"), max_words=12, max_characters=80)
            reasoning = _brief(_first(record, ("reasoning", "explanation", "rationale")), max_words=24, max_characters=180)
            value = _first(record, _VALUE_KEYS)
            source_reasoning = _related_source_reasoning(
                name,
                reasoning,
                matched_records,
                rule_records,
                action_records,
                risk_records,
            )
            cause = _cause_name(
                record,
                f"{reasoning} {source_reasoning}",
                scenario_category,
                name,
                dashboard_semantics,
            )
            identity = cause.casefold()
            if identity in seen:
                continue
            seen.add(identity)
            consequence = _narrative_value(
                dashboard_semantics,
                name,
                scenario_category,
                ("business_consequence", "business_impact", "impact_description"),
                ("business_impact_map", "business_consequence_map"),
                (
                    f"{cause} may affect {name}; validate the relationship against "
                    "the available dashboard and scenario evidence."
                ),
            )
            mitigation = _narrative_value(
                dashboard_semantics,
                name,
                scenario_category,
                ("mitigation", "recommended_mitigation", "response_guidance"),
                ("mitigation_map", "response_guidance_map"),
                (
                    f"Review evidence linked to {name}, validate the proposed driver, "
                    "and assign an accountable owner for follow-up."
                ),
            )
            evidence = _supporting_evidence(
                name,
                value,
                reasoning,
                scenario_text,
                rule_records,
                action_records,
                matched_records,
                risk_records,
            )
            confidence = _confidence(_first(record, _CONFIDENCE_KEYS))
            severity = _severity_score(impact, record)
            candidates.append(_filter_unlisted_domain_terms({
                "_rank": (
                    (severity or 0) * 100
                    + len(evidence) * 10
                    + (confidence * 20 if confidence is not None else 0)
                ),
                "root_cause": cause,
                "scenario_category": scenario_category.casefold(),
                "confidence": (
                    round(confidence, 2) if confidence is not None else None
                ),
                "confidence_reason": (
                    None
                    if confidence is not None
                    else "No source KPI confidence data was provided."
                ),
                "severity": (
                    {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW"}.get(
                        severity, "UNQUANTIFIED"
                    )
                ),
                "evidence": evidence,
                "business_consequence": consequence,
                "mitigation": mitigation,
                "recommended_mitigation": mitigation,
                "evidence_strength": None,
                "evidence_strength_reason": (
                    "Evidence strength is not calibrated from source data."
                ),
                "impact_score": None,
                "impact_score_reason": "No calibrated root-cause impact score is available.",
            }, dashboard_semantics))

        if not candidates:
            contextual_sources = [
                ("Dashboard", matched_records),
                ("Rule", rule_records),
                ("Risk", risk_records),
                ("Impact assessment", impact.get("dimensions", [])),
            ]
            for label, records in contextual_sources:
                if not isinstance(records, list):
                    continue
                for record in records[:_RECORD_LIMIT]:
                    if not isinstance(record, dict):
                        continue
                    name = _first(
                        record,
                        (*_NAME_KEYS, "rule_name", "dimension_name", "entity_name"),
                    )
                    if not name:
                        name = next(
                            (
                                key.replace("_", " ").title()
                                for key, value in record.items()
                                if key.casefold() not in {"id", "uuid", "entity_id"}
                                and value not in (None, "")
                            ),
                            "Business condition",
                        )
                    detail = _first(
                        record,
                        (
                            "reasoning",
                            "description",
                            "business_consequence",
                            "impact_description",
                            "risk",
                            "status",
                            "condition",
                        ),
                    )
                    cause = _cause_name(
                        record,
                        _brief(detail),
                        scenario_category,
                        _first(record, _NAME_KEYS),
                        dashboard_semantics,
                    )
                    if cause.casefold() in seen:
                        continue
                    seen.add(cause.casefold())
                    consequence = _narrative_value(
                        dashboard_semantics,
                        _first(record, _NAME_KEYS),
                        scenario_category,
                        ("business_consequence", "business_impact", "impact_description"),
                        ("business_impact_map", "business_consequence_map"),
                        (
                            f"{cause} may affect the observed business condition; "
                            "validate the relationship against available evidence."
                        ),
                    )
                    mitigation = _narrative_value(
                        dashboard_semantics,
                        _first(record, _NAME_KEYS),
                        scenario_category,
                        ("mitigation", "recommended_mitigation", "response_guidance"),
                        ("mitigation_map", "response_guidance_map"),
                        (
                            "Review linked dashboard and scenario evidence, validate "
                            "the proposed driver, and assign an accountable owner."
                        ),
                    )
                    evidence = [f"{label}: {_brief(name)}"]
                    if detail:
                        evidence.append(f"Context: {_brief(detail)}")
                    if scenario_text:
                        evidence.append(
                            f"Scenario: {_brief(scenario_text, max_words=12, max_characters=100)}"
                        )
                    confidence = _confidence(_first(record, _CONFIDENCE_KEYS))
                    severity = _severity_score(impact, record)
                    candidates.append(_filter_unlisted_domain_terms({
                        "_rank": (
                            (severity or 0) * 100
                            + len(evidence) * 10
                            + (confidence * 20 if confidence is not None else 0)
                        ),
                        "root_cause": cause,
                        "scenario_category": scenario_category.casefold(),
                        "confidence": (
                            round(confidence, 2) if confidence is not None else None
                        ),
                        "confidence_reason": (
                            None
                            if confidence is not None
                            else "No source KPI confidence data was provided."
                        ),
                        "severity": (
                            {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW"}.get(
                                severity, "UNQUANTIFIED"
                            )
                        ),
                        "evidence": evidence[:_EVIDENCE_LIMIT],
                        "business_consequence": consequence,
                        "mitigation": mitigation,
                        "recommended_mitigation": mitigation,
                        "evidence_strength": None,
                        "evidence_strength_reason": (
                            "Evidence strength is not calibrated from source data."
                        ),
                        "impact_score": None,
                        "impact_score_reason": (
                            "No calibrated root-cause impact score is available."
                        ),
                    }, dashboard_semantics))
                    if len(candidates) >= 5:
                        break
                if len(candidates) >= 5:
                    break

        if not candidates and scenario_text:
            cause = _cause_name(
                {},
                scenario_text,
                scenario_category,
                dashboard_semantics=dashboard_semantics,
            )
            consequence = _narrative_value(
                dashboard_semantics,
                "",
                scenario_category,
                ("business_consequence", "business_impact", "impact_description"),
                ("business_impact_map", "business_consequence_map"),
                "The scenario may affect business outcomes; validate impact using relevant evidence.",
            )
            mitigation = _narrative_value(
                dashboard_semantics,
                "",
                scenario_category,
                ("mitigation", "recommended_mitigation", "response_guidance"),
                ("mitigation_map", "response_guidance_map"),
                "Gather scenario-linked evidence and validate potential contributing factors.",
            )
            candidates.append(_filter_unlisted_domain_terms({
                "_rank": 20,
                "root_cause": cause,
                "scenario_category": scenario_category.casefold(),
                "confidence": None,
                "confidence_reason": "No source KPI confidence data was provided.",
                "severity": "UNQUANTIFIED",
                "evidence": [f"Scenario: {_brief(scenario_text, max_words=18, max_characters=140)}"],
                "business_consequence": consequence,
                "mitigation": mitigation,
                "recommended_mitigation": mitigation,
                "evidence_strength": None,
                "evidence_strength_reason": (
                    "Evidence strength is not calibrated from source data."
                ),
                "impact_score": None,
                "impact_score_reason": "No calibrated root-cause impact score is available.",
            }, dashboard_semantics))
        if not candidates:
            candidates.append({
                "_rank": 0,
                "root_cause": "Insufficient evidence to infer a likely driver",
                "scenario_category": scenario_category.casefold(),
                "confidence": None,
                "confidence_reason": "Insufficient evidence available.",
                "severity": "UNQUANTIFIED",
                "evidence": ["No scenario-linked KPI, rule, or dashboard evidence was available."],
                "business_consequence": "A material business consequence cannot be established from the available evidence.",
                "mitigation": "Gather scenario-relevant operating evidence and validate potential contributing factors.",
                "recommended_mitigation": "Gather scenario-relevant operating evidence and validate potential contributing factors.",
                "evidence_strength": None,
                "evidence_strength_reason": (
                    "Evidence strength is not calibrated from source data."
                ),
                "impact_score": None,
                "impact_score_reason": "No calibrated root-cause impact score is available.",
            })

        candidates.sort(key=lambda item: item["_rank"], reverse=True)
        return [
            {key: value for key, value in item.items() if key != "_rank"}
            for item in candidates[:5]
        ]
