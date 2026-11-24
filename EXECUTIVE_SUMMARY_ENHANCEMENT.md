# Executive Summary Enhancement

## Summary

Executive summaries now use three concise, labeled paragraphs: Business
Situation; Business Impact with Primary Risk; and Leadership Action. KPI
evidence may inform the narrative, but KPI names are not enumerated as a
substitute for explaining business consequences.

## Before example

> Customer satisfaction is weakening. NPS Trend matters because customer
> loyalty is falling. Review Rating also matters because reviews are worsening.
> Sentiment Alerts matters because negative feedback is increasing. Leadership
> should review the selected indicators.

This explains individual measures but does not clearly state the business
situation, material consequence, top concern, or immediate decision.

## After example

> Business Situation: For Retailer North, customer satisfaction declined by 12%
> over the past quarter.
>
> Business Impact: Declining customer loyalty may reduce repeat business.
> Primary Risk: Sentiment Alerts - Negative feedback is becoming more frequent.
>
> Leadership Action: Review service recovery priorities and address recurring
> issues to stabilize satisfaction and reduce churn risk.

The generated summary contains three paragraphs, explains the customer and
commercial consequences, identifies the selected risk, and recommends an
immediate leadership response without listing KPI names.

## Prompt and generation changes

- `ReportService` now deterministically formats the report summary using the
  three-paragraph executive structure. It derives the situation from the
  scenario, prioritizes business impact and the selected primary risk, and
  uses the selected action and expected outcome.
- The explainability prompt now requests exactly three labeled paragraphs,
  instructs the model to use KPI evidence internally, prohibits sequential KPI
  enumeration, and limits the summary to 100 words.
- The explainability fallback uses the same labels and avoids repeating
  selected KPI names in the impact and action paragraphs.
- The explanation model's field description documents the new structure.
- No simulation logic or risk-selection behavior changed.

## Test results

Added `app/tests/test_executive_summary.py` to compare a legacy KPI-listing
example against the generated executive narrative, validate the LLM prompt
instructions, and cover the unconfigured explainability fallback. Updated the
report structure assertion in `app/tests/test_semantic_authority.py`.

Validation command:

`python -m pytest app/tests/test_executive_summary.py app/tests/test_semantic_authority.py app/tests/test_dashboard_intelligence.py app/tests/test_root_cause_analysis.py -q`

Result: **76 passed**.

Additional workflow integration validation:

`python -m pytest app/tests/test_workflow_e2e.py app/tests/test_new_components.py -q`

Result: **9 passed**. Python compilation and `git diff --check` passed. Pylance
reported no summary-service diagnostics; it reported two existing unused
parameter warnings (`semantic_entities` and `recommendations`) in the
explainability interface.
