# Baseline Selection Review

## Selection algorithm

Scenario-matched monetary KPI candidates are ranked lexicographically by:

1. Semantic relevance
2. Dashboard relevance
3. Scenario match score
4. Source confidence

The highest-ranked candidate is exposed as `primary_baseline`. Remaining
candidates are exposed as `alternative_baselines`. Relevance metadata is read
from KPI records and the existing dashboard/selected-KPI records. Missing
ranking metadata does not create a score; it ranks below available positive
scores.

## Before and after calculations

- **Before:** Every directly matched monetary KPI could contribute its
  percentage-based estimate to the scenario total. Overlapping actual and
  forecast KPIs could therefore count the same exposure twice.
- **After:** Only `primary_baseline` contributes to the estimate and
  `amount_evidence`. Alternatives are returned for transparency and do not
  contribute to financial confidence/severity drivers or monetary totals. The
  existing percentage formula is unchanged.

Example for a 10% cashflow decrease:

```text
Before: Cashflow Actual (10M) + Cashflow Forecast (8M) => 1.8M estimated
After:  Cashflow Actual (10M) only                     => 1.0M estimated
```

In `include_full_state` responses, `state.baseline_selection` explicitly
contains the chosen baseline and informational alternatives. Each model
selection also logs `Selected primary baseline:` followed by the KPI name.

## Financial impact audit

- `financial_model_service.py` was the point where matched monetary KPI
  estimates were previously added together. The calculation now applies only
  to the selected primary candidate.
- `simulation_service.py` reads the financial model's already-selected
  single-baseline result; it does not aggregate KPI baseline values.
- `impact_analysis_service.py` reads the same scenario amount map and does not
  re-compute or add candidate KPI baselines.
- `dashboard_intelligence_service.py` ranks KPI candidates for relevance; it
  does not calculate financial exposure.
- Current enterprise exposure remains a separate collection of existing risk
  indicators and is not mixed into scenario-attributable estimates.

## Files changed

- `app/services/financial_model_service.py` — baseline ranking, output fields,
  and single-baseline calculation.
- `app/services/simulation_service.py` — forwards available relevance metadata.
- `app/services/impact_analysis_service.py` — forwards relevance metadata when
  it constructs the financial model.
- `app/api/routes.py` — exposes a concise baseline-selection object in
  `include_full_state` responses.
- `app/tests/test_runtime_request_context.py` — verifies full-state baseline
  validation output.
- `app/tests/test_financial_model_service.py` — overlap and priority regressions.
- `BASELINE_SELECTION_REVIEW.md` — this review.

## Tests added

- Cashflow actual versus forecast.
- Revenue versus revenue forecast.
- Collections versus collections forecast.
- Lexicographic semantic, dashboard, match, and confidence priority.

Each overlap regression checks the selected baseline, reported alternative,
single estimate, simulation total, and selection log. An additional regression
confirms an alternative's confidence does not affect the financial model.
The full-state API test verifies both baseline fields are returned.

Validation evidence:

- Focused financial-model and request-context tests: **47 passed**.
- Full offline test suite: **175 passed, 18 skipped**.
- `git diff --check` passed for the changed Python files.
