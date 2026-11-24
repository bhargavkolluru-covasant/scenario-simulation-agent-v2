# State Cleanup Report

## Changes

- Tenant and scope information is initialized and retained only under
  `context`.
- `scenario_semantics` is stored only at the state root; `scenario_context`
  retains classification and decision fields.
- Dashboard metadata is stored only under `dashboard_context`.
- Dashboard filter behavior derives from `dashboard_context.category_resolved`
  and `dashboard_context.allowed_kpi_terms`; redundant root flags are removed.
- Raw dashboard data and its consumed row/KPI projections remain available.
- Raw semantic reasoning is discarded after risk and action selection; duplicate
  `risk_context` is not persisted.
- The standard API response and report generation structure are unchanged.

## State size

Serialized-state size is measured with deterministic JSON serialization of the
same populated fixture. The legacy-size comparison restores the redundant
aliases, risk context, and consumed semantic response to the normalized state,
isolating the size contribution of those copies:

- Before normalization (legacy copies present): **3,536 bytes**
- After normalization: **2,503 bytes**
- Reduction: **1,033 bytes (29.2%)**

## Duplicate copies removed

- Root `enterprise_id`, `domain_ids`, and `scope_id` copies.
- Nested `scenario_context.scenario_semantics`.
- Root dashboard category, semantics, allowed groups/terms, and strict-filter
  aliases.
- `risk_context`, which duplicated the canonical primary and secondary risks.
- `semantic_reasoning` after its data has been consumed by risk/action selectors.

## Tests added

- Owner-node normalization reduces serialized state size.
- Canonical context, parsed scenario, scenario semantics, dashboard data, and
  dashboard context remain present.
- Report generation succeeds using the normalized state.
- Risk and action selectors retain their outputs while discarding consumed
  intermediate semantic state.
- Existing API request-context tests verify tenant fields are nested under
  `context` and no longer repeated at the state root.

Validation evidence: **68 targeted tests passed** across state normalization,
dashboard intelligence, semantic authority, API context, parser classification,
and workflow execution at the time of this report.

Final validation after the additional risk/semantic state cleanup: **176
passed, 18 skipped** in the full offline suite; the focused state and semantic
tests passed (**13 passed**). Pylance reported no syntax errors in the modified
Python files.
