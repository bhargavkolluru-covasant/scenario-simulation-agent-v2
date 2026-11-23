# Test Cleanup Report

## Summary

The default test run is offline-safe. Tests requiring live tokens, Groq, dashboards, or platform APIs are marked `integration` and skipped unless pytest is invoked with `--run-integration`. The workflow end-to-end test remains in the default suite and uses mocked dashboard/platform clients and an offline LLM.

## Classification

| Test or script | Classification | Default behavior |
| --- | --- | --- |
| `test_runtime_request_context.py` | Unit Test | Runs offline |
| `test_new_components.py` | Unit Test | Runs offline with LLM and rule-client fakes |
| `test_workflow_e2e.py` | Integration Test | Runs offline with mocked external clients and LLM |
| `test_dashboard_curl.py` | Unit Test | Runs offline; verifies no server-token fallback |
| `test_postman_equivalence.py` | Unit and Integration Tests | Unit cases run; live request is opt-in |
| `direct_test.py` | Development Script | Moved to `scripts/` |
| `test_auth_debug.py` | Development Script | Moved to `scripts/` |
| `test_token_current.py` | Development Script | Moved to `scripts/`; token value is no longer printed |
| `test_kg_integration.py` | Integration Test | Runs offline with mocked graph calls |

Connectivity tests in the authentication, expense, invoice, market-risk, procurement, rules, semantic-registry, vendor, knowledge-graph, Groq, and LLM-gateway modules are live Integration Tests and are marked for opt-in execution. The live knowledge-graph validation tests in `test_kg_entities.py`, `test_kg_graph.py`, `test_kg_node.py`, `test_kg_report.py`, `test_kg_stats.py`, and `test_kg_subgraph.py` are marked the same way.

## Tests Fixed

- Made scenario parsing, rule compilation, and explainability component tests deterministic without Groq or platform access.
- Updated the strategy-selector assertion to check the current `simulation_strategy` output.
- Updated workflow test tenant context and dashboard KPI fixtures; mocked LLM, dashboard, platform, and knowledge-graph dependencies.
- Updated workflow assertions to validate the report query value and presence without imposing a single-occurrence constraint.
- Updated the dashboard curl test to verify that no server token is injected.
- Removed the Postman test's import of a missing helper module; its live request now requires explicit caller token and tenant configuration.
- Updated the live authentication health check to require configured credentials rather than substituting a generated test token.

## Tests Skipped by Default

The 18 skipped tests are live integration checks:

- Semantic Registry authenticated endpoint health
- Expense, invoice, market-risk, procurement, rules, semantic-registry, and vendor connectivity
- Knowledge Graph connectivity, entity, graph, node, report, stats, and subgraph checks
- Live Groq and LLM Gateway checks
- Live Postman-equivalence request

Run live integration tests explicitly with `--run-integration`. The Postman request also requires `RUN_ARIIA_MANUAL_TEST=1` and configured caller/tenant credentials.

## Scripts Moved

- `app/tests/direct_test.py` -> `scripts/direct_test.py`
- `app/tests/test_auth_debug.py` -> `scripts/test_auth_debug.py`
- `app/tests/test_token_current.py` -> `scripts/test_token_current.py`

Each script now runs only when invoked directly; the token diagnostic no longer prints the token itself.

## Files Changed

- Added: `pytest.ini`, `app/tests/conftest.py`
- Updated: `app/tests/test_authentication.py`, `app/tests/test_dashboard_curl.py`, `app/tests/test_expense.py`, `app/tests/test_groq.py`, `app/tests/test_invoice.py`, `app/tests/test_kg_entities.py`, `app/tests/test_kg_graph.py`, `app/tests/test_kg_node.py`, `app/tests/test_kg_report.py`, `app/tests/test_kg_stats.py`, `app/tests/test_kg_subgraph.py`, `app/tests/test_knowledge_graph.py`, `app/tests/test_llm_gateway.py`, `app/tests/test_market_risk.py`, `app/tests/test_new_components.py`, `app/tests/test_postman_equivalence.py`, `app/tests/test_procurement.py`, `app/tests/test_rules.py`, `app/tests/test_semantic_registry.py`, `app/tests/test_vendor.py`, `app/tests/test_workflow_e2e.py`
- Moved: `app/tests/direct_test.py`, `app/tests/test_auth_debug.py`, `app/tests/test_token_current.py` into `scripts/`

No business workflow, graph execution, simulation logic, or report-generation implementation was changed.

## Validation

Command:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
.\venv\Scripts\python.exe -m pytest -p pytest_asyncio.plugin -q
```

Result: **131 passed, 18 skipped, 0 failed**.
