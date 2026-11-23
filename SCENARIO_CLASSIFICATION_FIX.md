# Scenario Classification Consistency Fix

## Root cause

`ScenarioIntentService` assigned `REVENUE_DECLINE` whenever the extracted
themes contained sales or revenue. The classifier ignored the structured
scenario's parsed `change_type`, so a revenue increase could be labeled as a
decline. The classifier node stored this result; semantic reasoning did not
change it, and strategy selection forwarded the same category.

## Before and after

- **Before:** `Revenue increases by 20%` could produce
  `scenario_category = decision_type = REVENUE_DECLINE`.
- **After:** Revenue `increase` maps to `REVENUE_GROWTH`; revenue `decrease`
  maps to `REVENUE_DECLINE`. Cost changes map to `COST_INCREASE` or
  `COST_DECREASE` according to the parsed direction.
- For a financial topic with no recognized parsed direction, the service uses
  a neutral `REVENUE_CHANGE` or `COST_CHANGE` category rather than guessing a
  direction.

`scenario_category`, `decision_type`, and semantic `intent_type` use the same
classification. The downstream strategy context preserves that category.

## Files modified

- `app/services/scenario_intent_service.py`
- `app/tests/test_scenario_classification.py`
- `SCENARIO_CLASSIFICATION_FIX.md`

## Tests added

Four offline workflow-path cases cover revenue increase/decrease and cost
increase/decrease. Each verifies the classification after parsing, intent
classification, semantic reasoning, and strategy selection.
