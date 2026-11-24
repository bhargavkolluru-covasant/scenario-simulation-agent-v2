# Dashboard Taxonomy Refactor

## Summary

Dashboard category and KPI context now come from the selected dashboard's
definition, metadata, description, and semantic metadata. The Python
`DASHBOARD_TAXONOMY` and `_CATEGORY_SIGNALS` are removed. A category is
`UNCLASSIFIED` when no category is explicitly supplied; words in the title,
description, widgets, or KPI names do not classify it.

KPI names and allowed KPI terms are collected from dashboard-provided KPI
definitions, terms, metric records, and widget titles. Business intent,
decision type, scenario types, KPI groups, risk groups, action groups, and
themes are populated only when present in the dashboard metadata. Unspecified
values remain empty instead of receiving domain-specific defaults.

## Metadata sources

The resolver reads fields from the dashboard definition and data payload,
including nested `metadata`, `dashboard_metadata`, `semantic_metadata`,
`dashboard_semantics`, and `semantics` objects. It accepts explicit `category`
or `dashboard_category` values and preserves arbitrary categories rather than
validating them against a fixed Python list. Existing explicit category
metadata in `dashboard_context` or `dashboard_category` remains a fallback.

## Validation

- Added resolver coverage for retail, logistics, and finance categories and
  their declared KPI and risk/action groups.
- Added a regression case showing real-estate terms alone produce
  `UNCLASSIFIED`.
- Added metadata pass-through coverage for an arbitrary category and a
  dashboard named Meridian Prime.
- `python -m pytest app/tests/test_dashboard_intelligence.py -q`: **32 passed**.
- Static search found no `DASHBOARD_TAXONOMY`, `_CATEGORY_SIGNALS`, or
  real-estate category/theme rules in `dashboard_intelligence_service.py`.

No Meridian Prime dashboard payload or pre-existing fixture was found in the
repository. The test verifies generic metadata preservation, but exact parity
with the deployed Meridian Prime dashboard cannot be confirmed until its
definition/semantic metadata is available.

## Scope notes

The specialized `rank_development_options` recommendation helper remains
unchanged because recommendation logic is explicitly out of scope. Its
development-specific metric handling is separate from dashboard
classification and the metadata-backed KPI taxonomy changed here.
