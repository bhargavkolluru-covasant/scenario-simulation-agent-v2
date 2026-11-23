# Scenario Simulation Agent — Review Remediation Plan

## Assessment scope

Compared the supplied review (for commit `c615b21`) with the workspace snapshot: project configuration and README, API and settings, workflow/state, simulation and financial model, LLM services, domain reasoning, clients, and the test tree. The findings below describe the current workspace, not a claim that the reviewer's test results were rerun here. No application code was changed and no tests were run for this planning task.

The review reports `116 passed, 7 failed, 9 skipped`, plus test collection problems. Those results are reviewer-reported; use the PR6 baseline run to establish the current branch's actual results.

## Executive summary

| Review issue | Finding in this workspace | Complexity | Planned PR |
|---|---|---:|---|
| 1. Caller authentication and tenant scope | Confirmed; request-body and server defaults can select credentials/tenant | High | PR1 |
| 2. Raw exception details in API response | Confirmed | Low | PR2 |
| 3. LLM provider routing | Confirmed; provider configuration and fallbacks could select non-Groq providers | Medium | PR3 |
| 4. Simulation and financial estimates | Confirmed; estimates are emitted under simulation labels | High | PR4 |
| 5. Unsupported risk/probability/confidence values | Confirmed | Medium | PR4 |
| 6. Overlapping monetary baselines | Confirmed | Medium | PR4 |
| 7. Direction and fallback parsing | Confirmed | Medium | PR4 |
| 8. Required/optional workflow failures | Failure swallowing confirmed; exact empty-completed case needs a regression test | High | PR2 |
| 9. Real-estate-specific reasoning | Confirmed across services and settings | High | PR5 |
| 10. Decision-service `/simulate` | Missing; no client or endpoint call found in this repository | High | PR4 |
| 11. Offline/reliable tests | Confirmed test issues and network-bound scripts; verify full suite in PR6 | Medium | PR6 |
| 12. State and node output hygiene | Confirmed duplicate field and in-place state mutation | Medium | PR6 |
| 13. Required service URLs and `.env.example` | Confirmed hardcoded defaults; example file absent | Low–Medium | PR6 |
| 14. Small, reviewable PRs | Process requirement, not a source-code defect | Low | PR6 / delivery practice |

---

## PR1 — Security: caller identity and tenant isolation

**Scope:** Issue 1 — do not let an unauthenticated caller invoke ARIIA APIs with service-configured credentials or tenant context.

**Exists?** Yes. `run_simulation` takes `access_token`, `enterprise_id`, and `domain_ids` from the JSON payload and falls back to settings. `ARIIA_ENTERPRISE_ID` and `ARIIA_DOMAIN_IDS` have real-estate defaults. `AuthService.get_token()` and `BaseClient._get_headers()` also fall back to `settings.access_token`; downstream clients fall back to settings for enterprise/domain headers. Thus removing only the request-model fields would not close the request-path fallback.

**Impacted files:** [app/api/routes.py](./app/api/routes.py), [app/config/settings.py](./app/config/settings.py), [app/services/auth_service.py](./app/services/auth_service.py), [app/clients/base_client.py](./app/clients/base_client.py), [app/state/simulation_state.py](./app/state/simulation_state.py), context/dashboard/client nodes under [app/nodes/](./app/nodes/), and [app/tests/test_authentication.py](./app/tests/test_authentication.py), [app/tests/test_runtime_request_context.py](./app/tests/test_runtime_request_context.py), [app/tests/test_workflow_e2e.py](./app/tests/test_workflow_e2e.py).

**Complexity:** High.

**Dependencies:** Confirm the platform's exact `Authorization`, `X-Enterprise-Id`, and `X-Domain-Id` contract and whether upstream services validate the token against the requested tenant. Decide whether local scripts retain a separate, explicitly non-request-path token mechanism.

**Risk of change:** High security impact if incomplete: any remaining fallback can preserve the confused-deputy behavior. Header/model changes also break current clients and test fixtures. Tenant-header matching alone is not proof of tenant authorization; the upstream authorization boundary must reject enterprise-A credentials scoped to enterprise B.

**Implementation approach:**
1. Make request authentication explicit: accept the bearer credential through FastAPI's Authorization header handling and require it; source enterprise/domain context from the specified headers. Remove credentials and tenant defaults from the request body.
2. Reject a missing credential with 401 and missing required tenant context with the agreed client error (review proposes 400).
3. Pass the caller context explicitly through workflow state and clients. Ensure request-path auth/client helpers never inject the server's token or tenant when caller context is absent. Keep any local-script credential opt-in isolated from the API path.
4. Remove hardcoded enterprise/domain defaults; update the API schema/example and deployment configuration.
5. Add route tests for missing auth/context and an isolation test proving tenant A's token cannot access tenant B (with a platform contract test if only the upstream service can establish that guarantee).

**Acceptance:** No server credential or tenant fallback is reachable from a simulation request; unauthenticated requests fail; cross-tenant access is rejected by the authorization boundary.

---

## PR2 — API Error Handling: safe responses and truthful run status

### Issue 2 — Do not return raw exception text

**Status:** Implemented for simulation execution errors. The API returns a generic body with a request ID, logs the ID with the exception, preserves the status of workflow-raised `HTTPException`s, and redacts exception strings from returned workflow/report data. BaseClient status-error logs no longer include upstream bodies.

**Impacted files:** [app/api/routes.py](./app/api/routes.py), [app/clients/base_client.py](./app/clients/base_client.py), and [app/tests/test_runtime_request_context.py](./app/tests/test_runtime_request_context.py).

**Complexity:** Low.

**Dependencies:** Agree on response shape for the friendly message and request ID; preserve structured server-side exception logging.

**Risk of change:** Low, but clients may currently depend on the accidental error detail. Ensure the request ID is useful in logs and does not expose internals.

**Implementation:** Generate a request ID for execution exceptions, return a fixed user-facing message with that ID, and log it with `logger.exception`. Tests cover node, HTTP client, and workflow failures, plus redaction of errors already present in returned workflow state.

### Issue 8 — Distinguish required failures from optional degradation

**Exists?** Partially confirmed. Many nodes catch broad exceptions and write placeholder/error-shaped values while returning state. For example, simulation writes `ERR-SIM`; the parser synthesizes a fallback scenario; report generation sets `COMPLETED` if report generation returns; and the API defaults missing status to `COMPLETED`. The exact reported empty-report path should be captured with a regression test rather than inferred from these patterns alone.

**Impacted files:** [app/graph/workflow.py](./app/graph/workflow.py), [app/api/routes.py](./app/api/routes.py), [app/state/simulation_state.py](./app/state/simulation_state.py), all failure-handling [app/nodes/](./app/nodes/) (especially `scenario_parser_node.py`, `dashboard_node.py`, `simulation_node.py`, `explainability_node.py`, `report_generation_node.py`), plus [app/tests/test_workflow_e2e.py](./app/tests/test_workflow_e2e.py) and [app/tests/test_new_components.py](./app/tests/test_new_components.py).

**Complexity:** High.

**Dependencies:** Classify nodes with product owners as required (at minimum scenario interpretation, dashboard evidence retrieval, and simulation) versus optional narrative/explanation. Decide the API status/error response contract.

**Risk of change:** High: graph termination and status semantics are externally visible, and treating an unavailable upstream as empty data could still produce a misleading report.

**Implementation approach:** Propagate failures from required steps to a terminal failed status and friendly API response; represent optional failures in a `degraded` field and continue only when the report remains useful. Remove success-shaped placeholders from required paths. Test required-node failure, optional-node failure, and LLM outage behavior end to end; never accept an empty report marked completed.

**PR dependencies:** PR2 should follow PR1's auth/request-context change in API tests. Failure policy should be agreed before PR4 replaces the simulation service.

---

## PR3 — LLM Integration: use Groq as the only provider

**Issue 3 — multiple configurable LLM providers and fallback paths**

**Previously confirmed?** Yes. The gateway registered Groq, Copilot, and Gemini; settings exposed provider selection and provider-specific credentials/models; and failed requests could fall through to another configured provider. The application now uses Groq exclusively.

**Impacted files:** [app/services/llm_gateway.py](./app/services/llm_gateway.py), [app/services/groq_service.py](./app/services/groq_service.py), [app/config/settings.py](./app/config/settings.py), [app/services/__init__.py](./app/services/__init__.py), [app/main.py](./app/main.py), [requirements.txt](./requirements.txt), [README.md](./README.md), and provider-related tests. The Copilot and Gemini service modules and Copilot-specific tests are removed.

**Status:** Implemented.

**Configuration:** Only `GROQ_API_KEY` and `GROQ_MODEL` configure the LLM provider. Groq timeout and retry defaults are internal service defaults.

**Implementation:** Route all gateway calls directly to `GroqService`; remove provider registration and fallback behavior; remove Copilot/Gemini settings, services, tests, and Gemini dependencies. Report Groq as the primary provider in startup logs and health output.

**Acceptance:** LLM execution follows `LLMGateway → GroqService → response`; no Copilot/Gemini provider registration, fallback, or local proxy is present.

---

## PR4 — Simulation Accuracy: label estimates, remove invented values, use causal output

### Issue 4 — Current implementation is not a causal simulation

**Exists?** Yes. `SimulationService.run()` counts records/actions/rules/graph nodes and delegates money calculations to a proportional estimate (`baseline × scenario percentage`). The result labels this `simulated_financial_exposure`; parsed `time_horizon` is not used by that calculation. The financial-model evidence does include an estimate caveat, but report-level simulation labels still overstate the result.

**Impacted files:** [app/services/simulation_service.py](./app/services/simulation_service.py), [app/services/financial_model_service.py](./app/services/financial_model_service.py), [app/models/simulation_models.py](./app/models/simulation_models.py), [app/nodes/simulation_node.py](./app/nodes/simulation_node.py), [app/services/report_service.py](./app/services/report_service.py), and related service/report tests.

**Complexity:** High.

**Dependencies:** Issue 10 integration and platform simulator contract. Before that integration lands, preserve honest estimate labels and an explicit method/caveat.

**Risk of change:** High: report fields and semantics are user-facing, and downstream consumers may expect current names. Avoid silently presenting provisional estimates as causal forecasts.

**Implementation approach:** In the interim, rename fields and report sections to indicate indicative estimates and include `method: proportional_estimate` plus the formula/caveat. When `/simulate` is integrated, make the causal response the source of projected impact numbers and retain the local estimate only if explicitly presented as a separate estimate.

### Issue 5 — Unsupported default risk, probability, confidence, and importance

**Exists?** Yes. `simulation_service.py` substitutes risk score `35.0` and calculates `impact_probability` from a hand-authored formula capped at `0.95`. `financial_model_service.py` substitutes confidence `0.5` for missing evidence, importance `0.6`, and model fallbacks `0.35`, `0.5`, and match quality `0.25`. Those values flow into apparently precise report fields.

**Impacted files:** [app/services/simulation_service.py](./app/services/simulation_service.py), [app/services/financial_model_service.py](./app/services/financial_model_service.py), [app/models/simulation_models.py](./app/models/simulation_models.py), [app/services/report_service.py](./app/services/report_service.py), and [app/tests/test_financial_model_service.py](./app/tests/test_financial_model_service.py).

**Complexity:** Medium.

**Dependencies:** PR4 field/response contract and consumer treatment of nullable measurements.

**Risk of change:** Medium–High: callers may assume numeric fields always exist. Nullability and reason fields need to be propagated to report rendering rather than replaced with zero or neutral values.

**Implementation approach:** Remove unsupported default values and probability formula. Return null/unavailable values with concise evidence-based reasons (for example, no risk KPI on the dashboard); list missing confidence/importance evidence. Keep measured source values distinct from derived or estimated values. Add no-evidence tests asserting null plus a reason.

### Issue 6 — Overlapping baselines are summed

**Exists?** Yes. The estimate loop adds proportional amounts from every eligible affected monetary KPI (up to ten), so distinct but overlapping measures such as actual and forecast can inflate the total. There is no `alternative_baselines` representation.

**Impacted files:** [app/services/financial_model_service.py](./app/services/financial_model_service.py), [app/tests/test_financial_model_service.py](./app/tests/test_financial_model_service.py), and report/model consumers.

**Complexity:** Medium.

**Dependencies:** Establish scenario-to-KPI matching and tie-breaking rules; coordinate with issue 10 so an estimate is not confused with causal projections.

**Risk of change:** Medium: estimated totals can materially change, and selecting a single baseline requires a transparent reason.

**Implementation approach:** Choose one best-matching monetary baseline, deterministically tie-break using match score (and a documented secondary rule), calculate only from it, and return other candidates as `alternative_baselines` without summing them. Test two overlapping cashflow KPIs.

### Issue 7 — Direction detection and parser fallback are unreliable

**Exists?** Yes. `_DIRECTION_TERMS` contains standalone `up` (so “follow up” may match as an increase) and lacks terms including “below”, “above”, “short of”, and “miss”. The heuristic parser extracts a percentage/horizon but defaults to `scenario_change` and does not reliably derive direction; on parse/provider failure it silently returns this fallback.

**Impacted files:** [app/services/financial_model_service.py](./app/services/financial_model_service.py), [app/services/scenario_parser_service.py](./app/services/scenario_parser_service.py), [app/models/scenario_models.py](./app/models/scenario_models.py), [app/nodes/scenario_parser_node.py](./app/nodes/scenario_parser_node.py), [README.md](./README.md), and [app/tests/test_new_components.py](./app/tests/test_new_components.py), [app/tests/test_financial_model_service.py](./app/tests/test_financial_model_service.py).

**Complexity:** Medium.

**Dependencies:** Agree on a structured scenario contract for direction/type, percentage, and horizon; PR3 provider reliability affects LLM parsing but must not justify fabricated fallbacks.

**Risk of change:** Medium–High: ambiguous input may now be rejected where it previously produced a guessed report. This is the intended safer behavior, but requires a clear rephrase prompt and client handling.

**Implementation approach:** Validate structured parser output with Pydantic and use it as the single source of truth. If parsing fails or required change details are absent, return a friendly request to rephrase instead of guessing. If a deterministic fallback remains, use phrase-aware rules and test README examples plus false positives such as “follow up on invoices”.

### Issue 10 — Use decision-service `/simulate`

**Exists?** Missing integration. Repository search finds no decision-service client or use of `projected_deltas`, `lever_changes`, or `max_hops`; `simulation_service.py` currently generates local outputs. The supplied review describes the external simulator but its source/contract is not included in this workspace, so field names and behavior must be verified against that service before implementation.

**Impacted files:** [app/services/simulation_service.py](./app/services/simulation_service.py), [app/clients/](./app/clients/), [app/models/simulation_models.py](./app/models/simulation_models.py), [app/nodes/simulation_node.py](./app/nodes/simulation_node.py), [app/services/impact_analysis_service.py](./app/services/impact_analysis_service.py), recommendation/report services and workflow tests.

**Complexity:** High.

**Dependencies:** Read the actual decision-service engine and route; confirm request/response schema, URL/config, tenant headers, `max_hops` bounds, and expected handling of `reason` responses. Depends on PR1 caller credentials/tenant headers. Requires fixtures or an integration environment for contract validation.

**Risk of change:** High: incorrect lever mapping or header propagation can produce misleading or cross-tenant output; service outages and “no edges” responses must not be converted into estimates. Existing report schema may need significant adjustment.

**Implementation approach:** Map validated parsed scenario KPI/direction/magnitude to the platform request; call with only the caller's authenticated tenant context. Feed `projected_deltas` into impact, recommendation, and report paths. If the simulator returns a reason or no deltas, report that validated relationships are unavailable; do not fill gaps with local guessed projections. Remove local number generation after parity and contract tests pass. Retain the current-exposure section only if it remains evidence-based and clearly separate.

**Acceptance:** Every number in simulation/impact sections traces to a simulator response or is visibly labeled as an estimate; “no validated edges” is reported plainly.

---

## PR5 — Domain-Agnostic Refactor

**Issue 9 — Real-estate rules in generic services**

**Exists?** Yes. `DASHBOARD_TAXONOMY` contains real-estate-specific HBU/GDV/IRR/hurdle and construction concepts. Real-estate vocabulary and outputs also appear in causal, root-cause, financial-reasoning, scenario-intent, strategy-selection, report, and explainability code; settings default to eight `re_...` domains. The README's examples and supported domains are also real-estate weighted. A query outside these domains can therefore receive inappropriate categories, causes, or actions.

**Impacted files:** [app/services/dashboard_intelligence_service.py](./app/services/dashboard_intelligence_service.py), [app/services/causal_reasoning_service.py](./app/services/causal_reasoning_service.py), [app/services/root_cause_analysis_service.py](./app/services/root_cause_analysis_service.py), [app/services/financial_reasoning_service.py](./app/services/financial_reasoning_service.py), [app/services/scenario_intent_service.py](./app/services/scenario_intent_service.py), [app/nodes/strategy_selector_node.py](./app/nodes/strategy_selector_node.py), [app/services/report_service.py](./app/services/report_service.py), [app/services/explainability_service.py](./app/services/explainability_service.py), [app/config/settings.py](./app/config/settings.py), [app/api/routes.py](./app/api/routes.py), [README.md](./README.md), and real-estate-biased fixtures in [app/tests/](./app/tests/).

**Complexity:** High.

**Dependencies:** Confirm where semantic registry/dashboard definitions store category, KPI groups, risk/action groups, and descriptions. The review explicitly calls for the registry source and a runtime configuration/document owner; those platform/UI details are not established by this repository snapshot.

**Risk of change:** High: removing specialized rules without equivalent registry semantics could regress current real-estate reports, while incomplete removal leaves non-real-estate domains biased. Avoid replacing Python constants with per-term environment variables.

**Implementation approach:** Inventory all non-test occurrences of the review's domain-specific terms and classify each as data-driven semantics versus domain-specific business logic. Resolve meaning from semantic registry/dashboard definitions. Where domain wording truly remains necessary, load it from one runtime-editable config document with an empty default. Remove hardcoded domain IDs and taxonomy defaults. Add a logistics fixture end-to-end test that asserts no unrelated real-estate wording and still verifies relevant evidence-driven output.

**Acceptance:** The review's grep criteria return no production Python occurrences of the listed real-estate terms/IDs; logistics test passes without suppressing valid platform-provided terminology.

---

## PR6 — Testing & Cleanup

### Issue 11 — Offline tests, collection failures, and stale assertions

**Exists?** Confirmed in the test sources, with current runtime failure counts not independently rerun. `test_postman_equivalence.py` imports `app.tests.test_dashboard_manual`, which is absent from the workspace. `direct_test.py` and `test_auth_debug.py` execute live HTTP requests at module import. The request-schema test still expects the old `"Bearer token"` example while the current schema example contains a masked value and will change with PR1. `test_new_components.py` hardcodes `gemini-1.5-pro` while settings specify `models/gemini-3.8-flash`; its parser expectation (`vendor_failure`) conflicts with the parser's generic fallback; and its strategy-node assertion expects `strategy` while the node writes `simulation_strategy`. Live connectivity tests are also present and need consistent opt-in handling. The review additionally reports LLM-outage failures in the explanation/workflow tests.

**Impacted files:** [app/tests/](./app/tests/) (especially `test_runtime_request_context.py`, `test_new_components.py`, `test_workflow_e2e.py`, `test_postman_equivalence.py`, `direct_test.py`, `test_auth_debug.py`, `test_dashboard_curl.py`, and connectivity tests such as `test_expense.py`, `test_invoice.py`, `test_knowledge_graph.py`, `test_market_risk.py`, `test_procurement.py`, `test_rules.py`, `test_semantic_registry.py`, and `test_vendor.py`).

**Complexity:** Medium.

**Dependencies:** Land or coordinate the API/LLM/parser/status contracts from PR1–PR4; explicitly identify integration test markers and the CI offline command.

**Risk of change:** Medium: moving scripts or changing collection patterns can accidentally remove useful manual diagnostics; tests that assert a stale contract may be “fixed” by weakening meaningful behavior checks.

**Implementation approach:** First establish an offline collection/test baseline. Update assertions to public settings/contracts rather than stale literals; decide whether the strategy contract should be `strategy` or `simulation_strategy` and keep implementation/test aligned. Mock LLM and platform clients in unit tests. Move standalone live scripts to `scripts/` (or otherwise make them non-collectable); mark live tests `integration` and skip unless explicitly enabled. Resolve or remove the broken import. Require `pytest app/tests -q` to pass offline with integration tests skipped by default.

### Issue 12 — State and graph hygiene

**Exists?** Yes. `SimulationState` declares `investment_prioritization` twice and contains a broad, loosely organized collection of optional fields. Nodes commonly mutate and return the entire state. The workflow is a sequential graph; opportunities for parallelism are optional and should not precede correctness work.

**Impacted files:** [app/state/simulation_state.py](./app/state/simulation_state.py), node functions under [app/nodes/](./app/nodes/), [app/graph/workflow.py](./app/graph/workflow.py), and workflow/node tests.

**Complexity:** Medium.

**Dependencies:** Stabilize state/API fields after PR1–PR5. Node output changes must follow LangGraph's expected state-update semantics and consider current tests/integrations.

**Risk of change:** Medium–High: removing fields or switching to partial updates can drop values consumed by downstream nodes; parallel graph execution can create state merge conflicts.

**Implementation approach:** Remove duplicate/unused fields and group related concepts only where types remain clear. Convert nodes incrementally to return only updated keys and add focused tests proving downstream state is preserved. Consider parallel independent nodes only after the sequential graph is correct and tested.

### Issue 13 — Environment URLs should be configured, not compiled in

**Exists?** Yes. `BASE_URL` and `PLATFORM_BACKEND_URL` default to production-like TRG Cloud Run addresses in settings; no `.env.example` exists at the project root.

**Impacted files:** [app/config/settings.py](./app/config/settings.py), clients using [app/config/settings.py](./app/config/settings.py) defaults, [README.md](./README.md), and a new `.env.example`.

**Complexity:** Low–Medium.

**Dependencies:** Deployment owners must provide required service URL names/values for local, test, and production environments. Coordinate with PR3 for LiteLLM configuration and PR4 for decision-service URL configuration.

**Risk of change:** Medium: making settings required can prevent startup in environments that currently rely on defaults. Add clear validation and migration/deployment instructions rather than a silent fallback.

**Implementation approach:** Remove hardcoded service URLs; make required endpoints explicit and fail startup/config validation when absent. Add a `.env.example` containing variable names and safe placeholders only; document setup and keep secrets out of the repository.

### Issue 14 — Small reviewable changes

**Exists?** This is a delivery/process requirement from the supplied review, not a runtime behavior defect established by source inspection. The requested six-PR structure provides a way to comply; this plan does not independently verify historical commit size.

**Impacted files:** No application file. PR descriptions, review boundaries, and optionally repository contribution guidance.

**Complexity:** Low.

**Dependencies:** Split implementation by the PR1–PR6 scopes below; do not combine unrelated changes merely to reduce PR count.

**Risk of change:** Low; the principal risk is overly broad PRs making security and behavior changes difficult to review or revert.

**Implementation approach:** Keep each PR focused, state behavior changed and test evidence in its description, and link related follow-up PRs. Do not rewrite history or amend existing commits as part of this remediation unless explicitly requested.

---

## Suggested delivery order and cross-PR dependencies

1. **PR1 Security** — establish caller-only auth and tenant context before adding new platform calls.
2. **PR2 API Error Handling** — safe API errors and explicit required/optional failure semantics.
3. **PR3 LLM Integration** — blocked on LiteLLM staging URL/key provisioning; can proceed independently once supplied.
4. **PR4 Simulation Accuracy** — issues 4–7 can be addressed with interim honest estimate semantics; issue 10 depends on PR1 and decision-service contract/access.
5. **PR5 Domain Agnostic Refactor** — depends on registry/config source-of-truth decisions and adds a non-real-estate fixture.
6. **PR6 Testing & Cleanup** — establish a baseline early if useful, but finish final suite/state/config cleanup after the behavior contracts stabilize. Each preceding PR should still add its own focused regression tests.

## Release acceptance checklist

- [ ] Caller token and tenant headers are mandatory; no server token/tenant fallback on the request path; cross-tenant access is rejected.
- [x] Unexpected simulation failures expose only generic text and a request ID; details remain in server logs.
- [ ] Required workflow failures cannot become an empty completed report; optional failures are explicitly marked degraded.
- [x] Groq is the only LLM provider; no alternate provider fallback is available.
- [ ] Every report number is measured, sourced from decision-service, or explicitly labeled as an estimate with its method and evidence.
- [ ] Missing evidence is represented as unavailable with a reason; overlapping estimates do not sum alternative baselines.
- [ ] README scenario examples and false-positive parsing cases have regression coverage.
- [ ] Decision-service “no validated edges” responses are reported without invented projections.
- [ ] Domain meaning comes from registry/runtime configuration; a non-real-estate fixture produces domain-appropriate output.
- [ ] Offline tests pass; network tests are opt-in integration checks.
- [ ] State cleanup preserves downstream behavior; URLs are configured externally and `.env.example` contains placeholders only.
- [ ] Remediation is delivered as small, independently reviewable PRs with test evidence.
