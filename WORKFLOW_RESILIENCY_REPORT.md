# Workflow Resiliency Report

## Required nodes

- `context`
- `scenario_parser`
- `dashboard_intelligence`
- `dashboard_context_resolver`
- `simulation`

Failures in these nodes set workflow status to `FAILED` and conditional graph
edges route directly to `END`.

## Optional nodes

- `explainability` → `explainability`
- `recommendation` → `recommendation_narrative`
- `report` → `report_enrichment`

Failures in these nodes are recorded in `degraded_features`; downstream nodes
continue and the final status is `COMPLETED_WITH_DEGRADED_FEATURES`. Report
output is checked so an empty report cannot be marked `COMPLETED`.

## Files changed

- `app/graph/workflow.py`
- `app/state/simulation_state.py`
- `app/nodes/scenario_parser_node.py`
- `app/nodes/simulation_node.py`
- `app/nodes/explainability_node.py`
- `app/api/routes.py`
- `app/tests/test_workflow_resiliency.py`
- `app/tests/test_runtime_request_context.py`
- `app/tests/test_workflow_e2e.py`

## Before and after

- **Before:** Several nodes swallowed failures or returned fallback results;
  required-node failures could continue through the graph, and report generation
  could set `COMPLETED` without validating report content.
- **After:** Required-node failures stop the graph and return status `FAILED`.
  Optional-node failures are listed in `degraded_features`, permit execution to
  continue, and return status `COMPLETED_WITH_DEGRADED_FEATURES`. Empty report
  output is classified as degraded.

## Test evidence

Added tests cover explainability, recommendation, dashboard, and simulation
failures, required-node graph stopping, empty reports, and the API failure
response. Existing full-state error-redaction coverage now exercises a degraded
report response.

Offline test command result: **143 passed, 18 skipped**.
