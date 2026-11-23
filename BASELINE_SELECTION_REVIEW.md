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
  `amount_evidence`. Alternatives are returned for transparency and never
  enter the total. The existing percentage formula is unchanged.

## Files changed

- `app/services/financial_model_service.py` — baseline ranking, output fields,
  and single-baseline calculation.
- `app/services/simulation_service.py` — forwards available relevance metadata.
- `app/services/impact_analysis_service.py` — forwards relevance metadata when
  it constructs the financial model.
- `app/tests/test_financial_model_service.py` — overlap and priority regressions.
- `BASELINE_SELECTION_REVIEW.md` — this review.

## Tests added

- Cashflow actual versus forecast.
- Revenue versus revenue forecast.
- Collections versus collections forecast.
- Lexicographic semantic, dashboard, match, and confidence priority.

Each overlap regression checks the selected baseline, reported alternative,
single estimate, and simulation total.
