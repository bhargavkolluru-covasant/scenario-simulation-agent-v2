# Risk and Confidence Audit

## Old behavior

- Simulation substituted `35.0` when no risk KPI was available and generated an
  impact probability from a hand-authored formula.
- Financial modeling substituted confidence, business-importance, and KPI-match
  values when the source did not provide them.
- Causal and root-cause analysis generated confidence values without source
  confidence evidence; missing evidence could be presented as a numeric score.
- Impact analysis translated qualitative financial severity and absent compliance
  findings into numeric dimension scores.
- Explainability rendered missing scenario confidence as `0%`.

## New behavior

- Missing risk scores and impact probabilities are `null` with reason fields;
  no impact probability is synthesized.
- Confidence is aggregated only from supplied KPI confidence fields. Missing
  confidence and numeric business-importance data remain `null` with reasons.
  Qualitative source importance labels remain qualitative rather than being
  converted to fabricated numeric scores.
- Root-cause confidence, evidence strength, and impact score remain unavailable
  unless supported by source data; each unavailable value has a reason.
- Uncalibrated financial and absent compliance dimension scores remain `null`.
  The overall impact score is `null` when no quantified dimensions are present.
- Explainability and reports identify unavailable confidence rather than
  displaying it as zero.

## Modified files

- `app/models/simulation_models.py`
- `app/services/simulation_service.py`
- `app/services/financial_model_service.py`
- `app/services/root_cause_analysis_service.py`
- `app/services/causal_reasoning_service.py`
- `app/services/dashboard_intelligence_service.py`
- `app/services/impact_analysis_service.py`
- `app/services/explainability_service.py`
- `app/services/report_service.py`
- `app/tests/test_financial_model_service.py`
- `app/tests/test_root_cause_analysis.py`
- `app/tests/test_kg_integration.py`

## Tests added or updated

- Added coverage for absent KPIs and absent risk metrics.
- Added coverage for missing confidence and business-importance evidence.
- Added no-evidence coverage for root-cause and overall impact scores.
- Added a regression test that prevents missing confidence from rendering as
  `0%`.
- Updated assertions that expected fabricated root-cause confidence or a
  numeric score when no risk KPI was present.

Validation: `136 passed, 18 skipped` with the offline pytest configuration.

## Remaining numeric literals

The requested literal search found no remaining active missing-data defaults.
Occurrences that remain are scoring/relevance thresholds and weights,
retry-backoff settings, or explicit test fixtures (including `0.35`, `0.25`,
`0.5`, `0.6`, and `0.95`). The historical `REVIEW_REMEDIATION_PLAN.md` also
describes the removed behavior; it is retained as review history and does not
participate in runtime execution.
