# Rule Filtering Refactor

## Summary

Enterprise rules are now filtered against the active dashboard and scenario
before entering workflow state. Root-cause analysis applies the same relevance
filter again before using rules as evidence, protecting direct service callers
that do not go through the workflow node.

## Audit

| Component | Finding | Change |
|---|---|---|
| `app/nodes/rules_node.py` | Retrieved up to 100 enterprise rules and passed every dictionary downstream without checking dashboard or scenario applicability. | Filters fetched rules using dashboard category, selected KPI/risk, parsed scenario category/type, and dashboard semantics. |
| `app/services/root_cause_analysis_service.py` | `_supporting_evidence` could cite any supplied rule with coincidental token overlap against a KPI or its reasoning. | Applies the relevance filter before rules are considered for root-cause and supporting evidence. |
| `app/services/rule_compilation_service.py` | The canonical fallback defaulted a missing business domain to `supply_chain` and emitted secondary-sourcing and invoice-review actions for any scenario. It compiles one scenario rule; it does not select from enterprise rules. | Missing domain now remains `UNCLASSIFIED`; fallback actions are domain-neutral evidence validation and accountable-owner notification. |
| `app/clients/rules_client.py` | Retrieves the enterprise rule list; it has no dashboard or selected scenario context and is not the appropriate filtering boundary. | Unchanged; filtering occurs after retrieval in `rules_node.py`. |
| `app/nodes/compile_rule_node.py` | Legacy compile node stores compiled output, but is not registered in the primary `app/graph/workflow.py` graph. | Audited; unchanged. |
| `app/services/rules_service.py` | No such file exists in the repository. Rule retrieval is implemented by `RulesClient`. | No change. |

## Filtering behavior

- Rejects rules whose declared dashboard/domain, scenario, KPI, or risk
  applicability conflicts with the selected context.
- Uses selected KPI definitions, risk names, scenario text/category, dashboard
  category/domain, and declared semantic groups to assess unscoped rules.
- Requires an exact selected KPI/risk phrase or at least two meaningful
  context-term matches for an unscoped rule; generic words such as “risk” and
  “alert” do not establish relevance by themselves.
- Honors rule IDs or names explicitly selected through dashboard context or
  dashboard semantic metadata, including intentional cross-domain selections.
- Filters rules in the root-cause service as well as the workflow node so
  unrelated enterprise rules cannot appear in its evidence section through a
  direct caller.

## Files changed

- `app/services/rule_relevance_service.py` — new shared applicability filter.
- `app/nodes/rules_node.py` — filters enterprise rules as they enter workflow
  state.
- `app/services/root_cause_analysis_service.py` — filters supplied rules before
  producing evidence.
- `app/services/rule_compilation_service.py` — removes supply-chain-only
  fallback domain/actions.
- `app/tests/test_rule_relevance_service.py` — adds domain, evidence, scope,
  explicit-selection, and compilation fallback coverage.

## Validation

Added workflow-node and root-cause evidence tests for:

- Customer Experience Dashboard — Customer Satisfaction and Sentiment Alerts.
- Retail Dashboard — Inventory Turnover and Stockout Risk.
- Logistics Dashboard — On-Time Delivery and Delivery Capacity Risk.

Each case includes unrelated lease-expiry, handover, GDV, and loan-facility
rules and verifies that the generated `Rule:` evidence contains only the
applicable rule. Additional cases verify that mismatched explicit applicability
is rejected, unscoped rules require substantive relevance, and dashboard
allowlisting can intentionally select a cross-domain rule.

Validation results:

- `python -m pytest app/tests/test_rule_relevance_service.py app/tests/test_root_cause_analysis.py app/tests/test_kg_integration.py app/tests/test_new_components.py app/tests/test_workflow_e2e.py app/tests/test_workflow_resiliency.py -q` — **59 passed**.
- `python -m compileall` for changed Python modules and tests — passed.
- Pylance syntax checks — no syntax errors.
- Pylance diagnostics for rule relevance and root-cause services — no
  diagnostics.
- `git diff --check` — passed.
