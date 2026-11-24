# Domain Reasoning Refactor

## Summary

Phase 4 replaces real-estate-specific causal, root-cause, and financial
narratives with reasoning grounded in the parsed scenario, selected KPIs and
risks, and dashboard semantic metadata. When evidence or semantic definitions
are missing, outputs use cautious generic language rather than guessing a
business cause or financial relationship.

## Files changed

- `app/services/causal_reasoning_service.py`
  - Builds causal paths from scenario, KPI, risk, and declared causal evidence.
  - Resolves categories from explicit scenario metadata, dashboard capabilities,
    or KPI metadata; otherwise returns `UNCLASSIFIED`.
  - Suppresses restricted real-estate terms in generated output unless they
    are explicitly present in dashboard semantics.
- `app/services/root_cause_analysis_service.py`
  - Resolves KPI meaning, root cause, business impact, and mitigation from
    semantic KPI definitions and mappings, including definitions keyed by KPI
    name.
  - Falls back to validation-oriented, KPI-linked hypotheses rather than
    category templates.
- `app/services/financial_reasoning_service.py`
  - Derives financial narratives from scenario context and selected KPI/risk
    evidence.
  - Removes invented quantitative relationships and domain-specific model
    selection; reports when evidence does not support a calculation.
- `app/services/impact_analysis_service.py`
  - Passes selected risks, scenario context, dashboard context, and dashboard
    semantics to causal analysis.
- `app/tests/test_root_cause_analysis.py`
  - Adds retail, logistics, and finance semantic-driven reasoning coverage,
    checks for unauthorized restricted terms, and verifies that explicit
    dashboard semantics may use domain-specific terms.
- `app/tests/test_kg_integration.py`
  - Replaces an expectation for a hardcoded handover-risk phrase with a check
    that reasoning does not introduce restricted terms absent from semantics.

## Removed assumptions

- Real-estate-specific root causes, delivery and handover risks, and
  category-selected recommendations.
- Hardcoded GDV optimization, HBU guidance, and hurdle-rate narratives.
- Financial estimates or investment conclusions without an explicit
  relationship and validated baseline.
- Implicit KPI meaning inferred from real-estate vocabulary or scenario
  category.

The restricted terms remain in the output-filtering safeguards and regression
tests; they are not used to select business logic. A term may pass through when
it is explicitly declared in dashboard semantics.

## Before and after

| Before | After |
|---|---|
| A project-delay or real-estate category could select a construction or handover root-cause narrative. | A root cause is taken from the selected KPI's semantic definition, a semantic mapping, or related evidence; otherwise the service returns a cautious hypothesis that requires validation. |
| Financial reasoning could apply GDV, HBU, hurdle-rate, or project-delay templates without dashboard evidence. | Financial reasoning summarizes the scenario and selected KPI/risk drivers, and explicitly states when a validated baseline or financial relationship is unavailable. |
| Retail or logistics scenarios could inherit real-estate explanations. | Retail, logistics, and finance tests supply their own KPI meanings and causes through dashboard semantics, and verify that unrelated real-estate terms do not appear in generated reasoning. |

## Validation

- `python -m pytest app/tests/test_root_cause_analysis.py app/tests/test_kg_integration.py app/tests/test_financial_model_service.py app/tests/test_dashboard_intelligence.py -q` — **96 passed**.
- `python -m compileall -q` for all four modified runtime services — passed.
- `git diff --check` — passed.
- Pylance syntax checks for all four modified runtime services — no syntax errors.
- Pylance signature compatibility checks — all 6 call sites of
  `CausalReasoningService.analyze` and all 6 call sites of
  `RootCauseAnalysisService.analyze` are compatible.
- Static search of the three target reasoning services found restricted terms
  only in suppression/allowlisting safeguards, not as hardcoded reasoning
  narratives.

## Scope

No workflow, parser, simulation engine, dashboard classification, report
generation, or recommendation-engine behavior was changed. The
`impact_analysis_service.py` change is limited to passing the requested
evidence and semantic context to causal analysis.
