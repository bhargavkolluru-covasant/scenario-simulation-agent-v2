# Simulation State Audit

## Ownership and duplication findings

| Field | Source owner | Duplicate locations | Recommendation |
|---|---|---|---|
| `enterprise_id` | Context layer | Root `enterprise_id` and `context.enterprise_id` | Keep only under `context`; update API initialization and platform-client nodes to read it there. |
| `domain_ids` | Context layer | Root `domain_ids` and `context.domain_ids` | Keep only under `context`. |
| `scope_id` | Context layer | Root `scope_id` and `context.scope_id` | Keep only under `context`. |
| `scenario` | Scenario parser | No equivalent state copy | Keep as the canonical parsed scenario. |
| `scenario_semantics` | Semantic/intent layer | Root `scenario_semantics` and `scenario_context.scenario_semantics` | Keep root `scenario_semantics`; keep classification/decision metadata in `scenario_context`. |
| `dashboard_data` | Dashboard layer | Raw dashboard payload is projected into `dashboard_rows` and `dashboard_widget_kpis` | Keep raw payload as canonical; retain derived rows and KPI records because separate consumers use these projections. Avoid serializing equivalent metadata aliases. |
| `dashboard_context` | Dashboard context resolver | Its `category`, `dashboard_semantics`, and allowed groups/terms were copied into root state fields | Keep metadata under `dashboard_context`; remove root aliases and read from the canonical object. |
| `strict_dashboard_filter` | Dashboard context resolver | Re-derived from `dashboard_context.category_resolved` and stored as a separate root flag | Derive from `dashboard_context.category_resolved`; do not persist a second flag. |
| `dashboard_definition` | Dashboard layer | Related to dashboard payload but represents definition metadata, not the same object | Keep separate; it is an independently sourced API result used to interpret raw data. |
| `matched_dashboard_records` | Entity matching layer | Subset/projection of `dashboard_rows` | Keep because downstream reasoning/reporting require matched results and it is not equivalent to all dashboard rows. |
| `selected_dashboard_kpi_names` | KPI selection layer | Derived from relevant records plus dashboard names | Keep as selector output; it is not identical to all dashboard KPI candidates. |
| `semantic_reasoning` | Semantic reasoning layer | Selected risk/action fields overlap with portions of the raw response | Keep it transiently until risk and action selectors consume it, then remove it from state. |
| `risk_context` | Risk selector | Duplicates `primary_risk` and `secondary_risk` with an extra source label | Do not persist; the canonical risk fields already identify the selected risks. |
| `final_report` | Report generation layer | Returned separately as the API `report` and included in full workflow state | Retain in full-state mode to preserve the API response contract. |

## Normalization decisions

- `context` owns request tenant/scope data after the context node.
- `scenario` remains the parser-owned canonical scenario.
- `scenario_semantics` is stored once at the top level; `scenario_context` owns
  classification and decision metadata only.
- `dashboard_context` owns dashboard category, dashboard semantics, allowed
  groups, and KPI terms. Selector flags are derived from this canonical object
  rather than copied to the root.
- Raw dashboard data and actively consumed derived projections remain available
  so workflow and report behavior is unchanged.
- Raw semantic reasoning is transient between reasoning and selector nodes;
  selected risk/action fields remain in their canonical locations.

The API's outer response keys and report-generation contract are unchanged.
`include_full_state` now shows the normalized canonical state rather than
repeating the listed metadata aliases.
