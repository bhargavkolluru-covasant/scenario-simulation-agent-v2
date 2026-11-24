import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
import logging 


logger = logging.getLogger(__name__)

_METADATA_CONTAINER_KEYS = ("metadata", "dashboard_metadata")
_SEMANTIC_CONTAINER_KEYS = ("semantic_metadata", "dashboard_semantics", "semantics")
_SEMANTIC_FIELDS = (
    "category", "dashboard_category", "business_domain", "domain",
    "description", "dashboard_description", "themes", "widget_titles",
    "kpi_groups", "kpi_terms", "kpi_names", "kpis", "kpi_definitions",
    "metrics", "metric_definitions", "risk_groups", "action_groups",
    "supported_scenario_types", "business_intent", "decision_type",
    "relevant_data_domain", "category_evidence",
)
_KPI_NAME_KEYS = ("name", "kpi_name", "metric_name", "title", "label", "display_name")
_CATEGORY_KEYS = ("category", "dashboard_category")
_IDENTITY_KEYS = (
    "option_id", "option_code", "development_option", "hbu_option",
    "option_name", "candidate_id", "candidate", "project_name", "name", "id",
)
_LABEL_KEYS = {
    "title", "name", "label", "display_name", "dashboard_title", "section",
    "section_name", "widget_title", "kpi_name", "metric_name", "metric",
    "description",
}
_VALUE_KEYS = ("value", "current_value", "metric_value", "score", "amount", "count")



def _normalized(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))

def _dashboard_metadata_layers(
    definition: Dict[str, Any],
    data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    layers: List[Dict[str, Any]] = []
    for root in (data, definition):
        layers.append(root)
        for container_key in _METADATA_CONTAINER_KEYS:
            container = root.get(container_key)
            if not isinstance(container, dict):
                continue
            layers.append(container)
            for semantic_key in _SEMANTIC_CONTAINER_KEYS:
                semantic = container.get(semantic_key)
                if isinstance(semantic, dict):
                    layers.append(semantic)
        for semantic_key in _SEMANTIC_CONTAINER_KEYS:
            semantic = root.get(semantic_key)
            if isinstance(semantic, dict):
                layers.append(semantic)
    return layers


def _metadata_value(
    layers: List[Dict[str, Any]],
    keys: Iterable[str],
    default: Any = None,
) -> Any:
    for layer in reversed(layers):
        for key in keys:
            value = layer.get(key)
            if value not in (None, ""):
                return value
    return default


def _metadata_text(value: Any) -> str:
    if isinstance(value, dict):
        value = next(
            (value[key] for key in ("name", "label", "value", "id") if value.get(key)),
            "",
        )
    return str(value).strip() if value is not None else ""


def _metadata_list(value: Any) -> List[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in value if item not in (None, "")]
    return [value]


def _semantic_metadata(layers: List[Dict[str, Any]]) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    for layer in layers:
        for container_key in _SEMANTIC_CONTAINER_KEYS:
            semantic = layer.get(container_key)
            if isinstance(semantic, dict):
                metadata.update(semantic)
        for key in _SEMANTIC_FIELDS:
            if key in layer and layer[key] not in (None, ""):
                metadata[key] = layer[key]
    return metadata


def _metadata_kpi_names(metadata: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for key in ("kpi_names", "metric_names", "kpis", "kpi_definitions", "metrics", "metric_definitions"):
        value = metadata.get(key)
        if isinstance(value, dict):
            values = (
                [value]
                if any(field in value for field in _KPI_NAME_KEYS)
                else list(value.values())
            )
        else:
            values = _metadata_list(value)
        for item in values:
            name = next(
                (item[field] for field in _KPI_NAME_KEYS if isinstance(item, dict) and item.get(field)),
                item if isinstance(item, str) else "",
            )
            if name:
                names.append(str(name).strip())
    return list(dict.fromkeys(names))


def _extract_dashboard_semantics(
    definition: Dict[str, Any],
    data: Dict[str, Any],
) -> Dict[str, Any]:
    layers = _dashboard_metadata_layers(definition, data)
    semantics = _semantic_metadata(layers)
    title = _metadata_text(
        _metadata_value(layers, ("title", "dashboard_title", "display_name", "name"), "")
    )
    description = _metadata_text(
        _metadata_value(layers, ("dashboard_description", "description", "summary"), "")
    )
    widgets = definition.get("widgets") or data.get("widgets") or []
    widget_titles = [
        str(widget.get("title", "")).strip()
        for widget in widgets
        if isinstance(widget, dict) and str(widget.get("title", "")).strip()
    ] if isinstance(widgets, list) else []

    semantics.setdefault("dashboard_name", title)
    semantics.setdefault("dashboard_description", description)
    semantics.setdefault(
        "business_domain",
        _metadata_text(_metadata_value(layers, ("business_domain", "domain"), "")),
    )
    semantics["themes"] = _metadata_list(semantics.get("themes"))
    semantics["widget_titles"] = _metadata_list(
        semantics.get("widget_titles") or widget_titles
    )
    semantics["widget_count"] = len(semantics["widget_titles"])
    return semantics

def _semantic_theme_score(
    kpi_name: str,
    dashboard_themes: List[str],
    scenario_themes: List[str],
) -> float:
    candidate_tokens = set(_normalized(kpi_name).split())
    context_tokens = set(
        _normalized(
            " ".join(str(theme) for theme in dashboard_themes + scenario_themes)
        ).split()
    )
    return (
        len(candidate_tokens.intersection(context_tokens))
        / max(len(candidate_tokens), 1)
    )

def _dashboard_labels(value: Any) -> List[str]:
    labels: List[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.casefold() in _LABEL_KEYS and isinstance(child, str):
                labels.append(child)
            labels.extend(_dashboard_labels(child))
    elif isinstance(value, list):
        for child in value:
            labels.extend(_dashboard_labels(child))
    return labels


def _metric_records(value: Any, terms: List[str]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    normalized_terms = [_normalized(term) for term in terms]

    def is_allowed(label: str) -> bool:
        normalized_label = _normalized(label)
        if not normalized_label:
            return False
        if not normalized_terms:
            return True
        return any(
            term in normalized_label
            for term in normalized_terms
            if len(term) > 2
        )

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            name = next(
                (
                    str(item[key])
                    for key in ("kpi_name", "metric_name", "name", "title", "label", "metric")
                    if item.get(key) not in (None, "")
                ),
                "",
            )
            metric_value = next(
                (item[key] for key in _VALUE_KEYS if item.get(key) not in (None, "")),
                None,
            )
            if name and metric_value is not None and is_allowed(name):
                records.append({
                    "name": name,
                    "value": metric_value,
                    "dashboard_evidence": True,
                })
            for key, child in item.items():
                if normalized_terms and is_allowed(key) and not isinstance(child, (dict, list)):
                    records.append({
                        "name": key.replace("_", " ").strip().title(),
                        "value": child,
                        "dashboard_evidence": True,
                    })
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    deduplicated: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for record in records:
        key = (_normalized(record["name"]), str(record["value"]))
        deduplicated[key] = record
    return list(deduplicated.values())


def resolve_dashboard_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve dashboard category and KPI meaning from supplied metadata only."""
    definition = state.get("dashboard_definition", {})
    data = state.get("dashboard_data", {})
    if not isinstance(definition, dict):
        definition = {}
    if not isinstance(data, dict):
        data = {}

    metadata_layers = _dashboard_metadata_layers(definition, data)
    dashboard_semantics = _extract_dashboard_semantics(definition, data)
    title = _metadata_text(
        _metadata_value(metadata_layers, ("title", "dashboard_title", "display_name", "name"), "")
    )
    category_value = _metadata_value(metadata_layers, _CATEGORY_KEYS)
    existing_context = state.get("dashboard_context")
    if not isinstance(existing_context, dict):
        existing_context = {}
    if category_value in (None, ""):
        category_value = (
            existing_context.get("category")
            or state.get("dashboard_category")
        )
    category = _metadata_text(category_value).upper() or "UNCLASSIFIED"
    category_resolved = category != "UNCLASSIFIED"

    labels = _dashboard_labels(definition) + _dashboard_labels(data)
    sections = [label for label in labels if "section" in label.casefold()]
    widget_names = [
        label for label in labels
        if any(key in label.casefold() for key in ("widget", "chart", "table"))
    ]
    dashboard_metric_names = [
        record["name"] for record in _metric_records(data, [])
    ]
    metadata_names = _metadata_kpi_names(dashboard_semantics)
    widget_metric_names = [
        part.strip()
        for widget_title in dashboard_semantics.get("widget_titles", [])
        if widget_title
        for part in re.split(r"\s+(?:and|&)\s+|[,|/]", str(widget_title), flags=re.IGNORECASE)
        if part.strip()
    ]
    kpi_names = list(dict.fromkeys(
        metadata_names + dashboard_metric_names + widget_metric_names
    ))
    allowed_kpi_terms = list(dict.fromkeys(
        [str(term) for term in _metadata_list(dashboard_semantics.get("kpi_terms"))]
        + kpi_names
    ))

    return {
        "title": title,
        "sections": sections,
        "widgets": widget_names,
        "kpi_names": kpi_names,
        "category": category,
        "category_resolved": category_resolved,
        "category_evidence": _metadata_list(
            _metadata_value(metadata_layers, ("category_evidence",), [])
        ),
        "business_intent": _metadata_text(dashboard_semantics.get("business_intent")),
        "decision_type": _metadata_text(dashboard_semantics.get("decision_type")),
        "relevant_data_domain": _metadata_text(
            dashboard_semantics.get("relevant_data_domain")
        ),
        "supported_scenario_types": _metadata_list(
            dashboard_semantics.get("supported_scenario_types")
        ),
        "allowed_kpi_groups": _metadata_list(dashboard_semantics.get("kpi_groups")),
        "allowed_kpi_terms": allowed_kpi_terms,
        "allowed_risk_groups": _metadata_list(dashboard_semantics.get("risk_groups")),
        "allowed_action_groups": _metadata_list(dashboard_semantics.get("action_groups")),
        "dashboard_semantics": dashboard_semantics,
    }

def select_relevant_kpis(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node 3: Relevant KPI Selector
    Build a dashboard-scoped KPI pool and rank candidates using dashboard,
    scenario, entity, semantic, and confidence relevance.
    Returns 1 Primary KPI and 2 Supporting KPIs.
    """
    dashboard_context = state.get("dashboard_context", {})
    if not isinstance(dashboard_context, dict):
        dashboard_context = {}
    logger.info(
    "[KPI DEBUG] widget_kpis=%s",
    state.get(
        "dashboard_widget_kpis",
        []
    ),
)
    dashboard_semantics = dashboard_context.get("dashboard_semantics")
    if not isinstance(dashboard_semantics, dict):
        dashboard_semantics = state.get("dashboard_semantics")
    if not isinstance(dashboard_semantics, dict):
        dashboard_semantics = {}

    scenario_semantics = state.get("scenario_semantics")
    if not isinstance(scenario_semantics, dict):
        scenario_semantics = {}
    terms = dashboard_context.get("allowed_kpi_terms", [])
    if not isinstance(terms, list):
        terms = []

    dashboard_data = state.get("dashboard_data", {})
    rows = state.get("dashboard_rows", [])
    records = _metric_records(dashboard_data, terms)
    records.extend(_metric_records(rows, terms))

    unique_records: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for record in records:
        key = (_normalized(record["name"]), str(record["value"]))
        unique_records[key] = record

    scenario = state.get("scenario", {})
    query = str(state.get("query") or "")
    scenario_text = " ".join(
        [query]
        + [
            str(value)
            for value in scenario.values()
            if value not in (None, "")
        ]
        if isinstance(scenario, dict)
        else [query, str(scenario)]
    ).casefold()

    target_entity = str(
        state.get("primary_business_entity")
        or (scenario.get("target_entity") if isinstance(scenario, dict) else "")
        or ""
    )

    dashboard_category = str(
        dashboard_context.get("category") or state.get("dashboard_category") or ""
    ).upper()

    # Collect all candidates: dashboard records + incoming KPI insights
    kpi_insights = state.get("kpi_insights") or {}
    raw_kpis = []
    if isinstance(kpi_insights, dict):
        raw_kpis = kpi_insights.get("kpis") or []
    elif isinstance(kpi_insights, list):
        raw_kpis = kpi_insights

    all_candidates: List[Dict[str, Any]] = (
    list(unique_records.values())
    +
    state.get(
        "dashboard_widget_kpis",
        [],
    )
)
    logger.info(
    "[KPI DEBUG] total_candidates=%d",
    len(all_candidates),
)
    logger.info(
    "[KPI DEBUG] candidates=%s",
    [
        (
            c.get("name")
            or c.get("title")
        )
        for c in all_candidates[:20]
    ],
)
    for item in raw_kpis:
        if isinstance(item, dict):
            name = next(
                (item[key] for key in ("kpi_name", "metric_name", "name", "title", "label", "metric") if item.get(key)),
                "",
            )
            val = next((item[key] for key in _VALUE_KEYS if item.get(key) is not None), None)
            if name and val is not None:
                all_candidates.append(item)

    primary_kpi, supporting_kpis, scored_candidates = rank_kpis_by_formula(
        candidates=all_candidates,
        dashboard_category=dashboard_category,
        scenario_text=scenario_text,
        target_entity=target_entity,
        allowed_terms=terms,
        dashboard_themes=dashboard_semantics.get("themes", []),
        scenario_themes=scenario_semantics.get("themes", []),
        dashboard_kpi_names=(
            state.get("selected_dashboard_kpi_names")
            or dashboard_context.get("kpi_names", [])
        ),
        widget_titles=dashboard_semantics.get("widget_titles", []),
    )
    dashboard_names = dashboard_context.get("kpi_names", [])
    selected_names = list(dict.fromkeys(
        [str(record.get("name") or record.get("kpi_name")) for record in scored_candidates if record.get("name") or record.get("kpi_name")]
        + [str(name) for name in dashboard_names if name]
    ))

    return {
        "dashboard_kpi_records": scored_candidates,
        "selected_dashboard_kpi_names": selected_names,
        "primary_kpi": primary_kpi,
        "supporting_kpis": supporting_kpis,
    }


def rank_kpis_by_formula(
    candidates: List[Dict[str, Any]],
    dashboard_category: str,
    scenario_text: str,
    target_entity: str,
    allowed_terms: List[str],
    dashboard_themes: Optional[List[str]] = None,
    scenario_themes: Optional[List[str]] = None,
    dashboard_kpi_names: Optional[List[str]] = None,
    widget_titles: Optional[List[str]] = None,
)-> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Rank candidate KPIs using dashboard, scenario, entity, semantic, and confidence relevance.
    """
    normalized_scenario = _normalized(scenario_text)
    normalized_entity = _normalized(target_entity)
    dashboard_labels = {
        _normalized(label)
        for label in (dashboard_kpi_names or []) + (widget_titles or [])
        if _normalized(label)
    }

    scored_list = []
    seen_identities = set()

    for item in candidates:
        if not isinstance(item, dict):
            continue
        name = next(
            (str(item[key]) for key in ("kpi_name", "metric_name", "name", "title", "label", "metric") if item.get(key)),
            "",
        )
        if not name:
            continue
        value = next(
            (item[key] for key in _VALUE_KEYS if item.get(key) is not None),
            "",
        )
        identity = (_normalized(name), str(value))
        if identity in seen_identities:
            continue
        seen_identities.add(identity)

        semantic_score = (
            _semantic_theme_score(
                name,
                dashboard_themes or [],
                scenario_themes or [],
            )
        )

        norm_name = _normalized(name)
        name_tokens = set(norm_name.split())
        dashboard_rel = max(
            (
                len(name_tokens.intersection(label.split()))
                / max(len(name_tokens.union(label.split())), 1)
                for label in dashboard_labels
            ),
            default=0.0,
        )
        if norm_name in dashboard_labels:
            dashboard_rel = 1.0

        scenario_tokens = set(normalized_scenario.split())
        candidate_text = " ".join(
            str(value)
            for key, value in item.items()
            if not str(key).startswith("_") and value not in (None, "")
        )
        candidate_tokens = set(_normalized(candidate_text).split())
        scenario_rel = (
            len(candidate_tokens.intersection(scenario_tokens))
            / max(len(candidate_tokens), 1)
        )

        record_text = " ".join(str(v) for v in item.values()).casefold()
        if normalized_entity and normalized_entity in record_text:
            entity_rel = 1.0
        elif normalized_entity and any(tok in record_text for tok in normalized_entity.split()):
            entity_rel = 0.7
        else:
            entity_rel = 0.4

        # 4. Confidence (10%)
        raw_conf = next(
            (
                item[key]
                for key in ("confidence_score", "confidence")
                if item.get(key) not in (None, "")
            ),
            None,
        )
        conf = None
        confidence_reason = None
        try:
            if raw_conf is not None:
                conf = float(raw_conf)
                if conf > 1.0:
                    conf /= 100.0
                conf = min(max(conf, 0.0), 1.0)
        except (ValueError, TypeError):
            confidence_reason = "Source KPI confidence was not numeric."
        if conf is None and confidence_reason is None:
            confidence_reason = "No source KPI confidence data was provided."

        score_components = [
            (0.25, dashboard_rel),
            (0.25, scenario_rel),
            (0.20, entity_rel),
            (0.20, semantic_score),
        ]
        if conf is not None:
            score_components.append((0.10, conf))
        total_score = round(
            sum(weight * score for weight, score in score_components)
            / sum(weight for weight, _ in score_components),
            4,
        )

        item_copy = dict(item)
        item_copy["name"] = name
        item_copy["value"] = value
        item_copy["_scoring"] = {
            "dashboard_relevance": dashboard_rel,
            "scenario_relevance": scenario_rel,
            "entity_relevance": entity_rel,
            "semantic_relevance": semantic_score,
            "confidence": conf,
            "confidence_reason": confidence_reason,
            "total_score": total_score,
        }
        scored_list.append(item_copy)

    # Sort descending by formula total_score
    scored_list.sort(key=lambda x: x["_scoring"]["total_score"], reverse=True)

    if not scored_list:
        return None, [], []

    # 1 Primary KPI, 2 Supporting KPIs
    p_candidate = scored_list[0]
    p_name = p_candidate["name"]
    p_val = p_candidate["value"]
    unit = p_candidate.get("kpi_unit") or p_candidate.get("unit") or ""
    display_val = f"{p_val}{unit}" if unit and unit not in str(p_val) else str(p_val)

    why_it_matters = str(
        p_candidate.get("reasoning")
        or p_candidate.get("explanation")
        or f"{p_name} is the highest-ranked dashboard indicator for this scenario."
    )
    business_relevance = f"Dashboard and scenario evidence make {p_name} relevant to this assessment."

    primary_kpi = {
        "name": p_name,
        "value": display_val,
        "raw_value": p_val,
        "unit": unit,
        "why_it_matters": why_it_matters,
        "business_relevance": business_relevance,
        "confidence": p_candidate["_scoring"]["confidence"],
        "confidence_score": p_candidate["_scoring"]["confidence"],
        "confidence_reason": p_candidate["_scoring"]["confidence_reason"],
        "total_score": p_candidate["_scoring"]["total_score"],
    }

    supporting_kpis = []
    for s_candidate in scored_list[1:3]:
        s_name = s_candidate["name"]
        s_val = s_candidate["value"]
        s_unit = s_candidate.get("kpi_unit") or s_candidate.get("unit") or ""
        s_display = f"{s_val}{s_unit}" if s_unit and s_unit not in str(s_val) else str(s_val)
        s_evidence = str(
            s_candidate.get("reasoning")
            or s_candidate.get("explanation")
            or f"Provides essential quantitative cross-validation for {p_name}."
        )
        supporting_kpis.append({
            "name": s_name,
            "value": s_display,
            "raw_value": s_val,
            "unit": s_unit,
            "evidence": s_evidence,
            "confidence": s_candidate["_scoring"]["confidence"],
            "confidence_reason": s_candidate["_scoring"]["confidence_reason"],
            "total_score": s_candidate["_scoring"]["total_score"],
        })

    return primary_kpi, supporting_kpis, scored_list


def kpi_is_dashboard_relevant(
    name: Any,
    allowed_terms: List[str],
    dashboard_kpi_names: List[str],
) -> bool:
    normalized_name = _normalized(name)
    if not normalized_name:
        return False
    normalized_names = {_normalized(item) for item in dashboard_kpi_names}
    if normalized_name in normalized_names:
        return True
    return any(
        _normalized(term) in normalized_name
        for term in allowed_terms
        if len(_normalized(term)) > 2
    )


def rank_development_options(rows: Any) -> List[Dict[str, Any]]:
    """
    Capital Allocation Rule:
    Generate:
    - Investment Ranking (Priority 1, 2, 3)
    - Recommended Options
    - Deferred Options
    - Clear feasibility rationale with Weighted Score, IRR, Hurdle Rate, GDV, Development Cost, Zoning Confidence.
    """
    if not isinstance(rows, list):
        return []
    candidates: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = {_normalized(key): value for key, value in row.items()}
        label = next(
            (
                str(row[key])
                for key in _IDENTITY_KEYS
                if row.get(key) not in (None, "")
            ),
            "",
        )
        if not label or _normalized(label) in {
            "weighted score",
            "hbu score",
            "irr",
            "gdv",
            "development cost",
            "hurdle rate",
            "zoning confidence",
        }:
            continue
        values = {
            "weighted_score": _find_number(normalized, ("weighted score", "hbu score", "score")),
            "irr": _find_number(normalized, ("irr", "internal rate of return")),
            "gdv": _find_number(normalized, ("gdv", "gross development value")),
            "development_cost": _find_number(normalized, ("development cost", "total cost", "cost")),
            "hurdle_rate": _find_number(normalized, ("hurdle rate",)),
            "zoning_confidence": _find_number(normalized, ("zoning confidence",)),
        }
        if not any(value is not None for value in values.values()):
            continue
        candidates.append({"option": label, **values})

    candidates.sort(
        key=lambda item: (
            item["irr"] is None
            or item["hurdle_rate"] is None
            or item["irr"] >= item["hurdle_rate"],
            item["weighted_score"] is not None,
            item["weighted_score"] if item["weighted_score"] is not None else float("-inf"),
            item["irr"] if item["irr"] is not None else float("-inf"),
            item["zoning_confidence"] if item["zoning_confidence"] is not None else float("-inf"),
        ),
        reverse=True,
    )
    for index, item in enumerate(candidates[:3], start=1):
        rationale = []
        if item["weighted_score"] is not None:
            rationale.append(f"weighted score {item['weighted_score']:g}")
        if item["irr"] is not None and item["hurdle_rate"] is not None:
            meets_hurdle = item["irr"] >= item["hurdle_rate"]
            rationale.append(
                f"IRR {item['irr']:g}% remains above the {item['hurdle_rate']:g}% hurdle rate"
                if meets_hurdle
                else f"IRR {item['irr']:g}% falls below the {item['hurdle_rate']:g}% hurdle rate and requires deferral"
            )
        elif item["irr"] is not None:
            rationale.append(f"IRR {item['irr']:g}%")
        if item["gdv"] is not None:
            rationale.append(f"GDV AED {item['gdv']:g}M" if item['gdv'] < 1000 else f"GDV AED {item['gdv']:,.0f}")
        if item["development_cost"] is not None:
            rationale.append(f"Development Cost AED {item['development_cost']:g}M" if item['development_cost'] < 1000 else f"Development Cost AED {item['development_cost']:,.0f}")
        if item["zoning_confidence"] is not None:
            rationale.append(f"zoning confidence {item['zoning_confidence']:g}")

        item["priority"] = index
        item["candidate_category"] = (
            "Primary Candidate" if index == 1
            else "Secondary Candidate" if index == 2
            else "Deferred Candidate"
        )
        item["rationale"] = (
            "Highest " + ", ".join(rationale)
            if index == 1 and rationale
            else ", ".join(rationale) if rationale
            else "Highest remaining risk-adjusted value based on available feasibility evidence"
        )

    return candidates[:3]


def _find_number(values: Dict[str, Any], terms: Tuple[str, ...]) -> Any:
    for key, value in values.items():
        if any(term in key for term in terms):
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                match = re.search(r"(\d+(?:\.\d+)?)", value.replace(",", ""))
                if match:
                    return float(match.group(1))
    return None
