# Domain-Agnostic Migration Plan

This plan follows the findings in [REAL_ESTATE_DEPENDENCY_AUDIT.md](./REAL_ESTATE_DEPENDENCY_AUDIT.md). It is an implementation proposal only: **no application behavior or code has been changed**.

## Goal

Make dashboard interpretation and scenario outputs depend on the selected dashboard's semantic definition, measured evidence, validated relationships, and approved runtime policies—not real-estate-specific Python constants or generic-sounding assumptions.

## Affected files and complexity

| File | Main coupling | Complexity | Proposed replacement source |
|---|---|---:|---|
| [app/services/dashboard_intelligence_service.py](./app/services/dashboard_intelligence_service.py) | `DASHBOARD_TAXONOMY`, `_CATEGORY_SIGNALS`, development option KPI alias extraction/ranking, thresholds, AED display | High | Semantic registry/dashboard definition for category, business domain, KPI aliases/types/units; approved runtime policy for any applicable ranking rule |
| [app/services/causal_reasoning_service.py](./app/services/causal_reasoning_service.py) | Construction/handover keyword classification and fixed operational delay-to-risk chain | High | Structured scenario semantics plus validated graph relationships; return no causal chain when evidence is unavailable |
| [app/services/root_cause_analysis_service.py](./app/services/root_cause_analysis_service.py) | Construction/handover cause overrides, fixed consequences, injected critical-path mitigation | High | Evidence-linked dashboard/rule/action records, validated graph evidence, semantic-registry risk descriptions, platform action catalogue |
| [app/services/financial_reasoning_service.py](./app/services/financial_reasoning_service.py) | Fixed development strategy, 12% hurdle, fabricated examples, asset-value and collections assumptions, canned actions | High | Approved runtime financial policy/formula and measured dashboard inputs; platform actions; otherwise report limitations without projection |
| [app/services/report_service.py](./app/services/report_service.py) | Handover/HBU field aliases, option-specific renderer, hardcoded KPI interpretations and project narrative | High | KPI/entity schemas and display metadata from the semantic registry/dashboard definition; generic evidence renderer |
| [app/services/scenario_intent_service.py](./app/services/scenario_intent_service.py) | HBU/GDV/handover keyword-to-theme mapping | Medium | Parsed structured intent plus dashboard-provided semantic themes |
| [app/nodes/strategy_selector_node.py](./app/nodes/strategy_selector_node.py) | `LAND_FEASIBILITY` and keyword-to-strategy/methodology rules | Medium | Registry/dashboard capability-to-strategy mapping; explicit unknown/default path |
| [app/services/explainability_service.py](./app/services/explainability_service.py) | Handover-specific context-field whitelist | Low–Medium | Schema-driven field selection from dashboard/KPI metadata |
| [app/api/routes.py](./app/api/routes.py) | Real-estate OpenAPI example query | Low | Domain-neutral API example or example derived from a neutral test fixture |
| [app/config/settings.py](./app/config/settings.py) | No `re_*` defaults found in the current snapshot | None for this issue | No change expected; preserve externally supplied tenant/domain context |

### Overall complexity: High

Most individual display/alias changes are moderate, but the refactor affects how dashboards are categorized, which KPI data is selected, how root causes and risks are justified, and what recommendations are emitted. The semantic-registry schema and ownership must be established before removing the Python taxonomy, or the system will lose information rather than become generic.

## Dependency order

### 0. Define contracts and source of truth

**Prerequisite:** Confirm where the semantic registry and dashboard definition store:

- dashboard category/business domain and themes;
- KPI names, IDs, aliases, value types, units, and currency;
- semantic groups for risks and actions;
- descriptions and domain-specific formula/policy metadata;
- provenance/versioning and tenant/domain scope.

**Replacement source:** Semantic registry and selected dashboard definition. For formulas or decision policies, use a separately governed runtime policy only if that platform source exists and is authoritative. Do not copy the existing Python constants into environment variables.

### 1. Add/verify a generic semantic adapter

Create or extend the shared mapping from registry/dashboard payloads into typed generic dashboard semantics. Define explicit behavior for absent, malformed, or ambiguous metadata: retain `UNCLASSIFIED`/unknown values and avoid guessing. Confirm the adapter works on fixtures for a current dashboard and at least one logistics dashboard.

**Depends on:** Step 0.

### 2. Remove hardcoded dashboard taxonomy and KPI extraction

Refactor `dashboard_intelligence_service.py` to resolve categories, KPI aliases, and descriptions from the semantic adapter. Remove the special development-option ranking path from the generic code; if it is still a supported domain capability, implement it as a registry-declared strategy/policy with domain-owned tests and clear invocation gating.

**Depends on:** Steps 0–1.

### 3. Make intent and strategy selection semantic

Refactor `scenario_intent_service.py` and `strategy_selector_node.py` to consume parsed scenario fields and dashboard registry capabilities rather than searching for HBU/GDV/handover terms. Keep fallback behavior neutral and explicit when no strategy mapping exists.

**Depends on:** Steps 0–1; can proceed alongside Step 2 after the contract stabilizes.

### 4. Remove unsupported root-cause and causal rules

Refactor `causal_reasoning_service.py` and `root_cause_analysis_service.py` to use source KPI/rule/action evidence and validated graph edges. Remove fixed causal propagation and keyword-driven overrides. Pull risk text from registry definitions and mitigation options from the platform action service. Preserve “unknown/no validated relationship” outcomes rather than substituting generic guesses.

**Depends on:** Steps 0–1; graph relationship semantics and action-service contract must be confirmed.

### 5. Replace domain-specific financial reasoning

Refactor `financial_reasoning_service.py` so that financial conclusions require measured input plus a sourced, applicable formula/policy. Remove the fixed hurdle threshold, sample candidate IDs/values, assumed cash-flow/contract effects, and canned domain recommendations. Use approved runtime methodology only when it is explicit and versioned.

**Depends on:** Step 0 and the platform's policy/formula ownership; causal claims also depend on Step 4.

### 6. Make reporting and explanation schema-driven

Refactor `report_service.py` and `explainability_service.py` to render selected evidence and registry-provided labels/units generically. Replace HBU/handover-specific field aliases and renderers with semantic type/schema definitions. Keep names and descriptions from the selected dashboard; do not normalize unknown business concepts into real-estate terms.

**Depends on:** Steps 0–2; output labels should align with the new semantic schema.

### 7. Validate and remove residual branding/examples

Use a neutral API example in `routes.py`. Add/retain contract tests for current real-estate data and non-real-estate fixtures, and search all runtime Python again for the audit terms and `re_*` identifiers. Review each remaining hit rather than requiring zero hits blindly: domain text originating from registry data is valid and should not be deleted.

**Depends on:** Steps 2–6.

## Recommended replacement-source hierarchy

1. **Dashboard definition / semantic registry:** selected dashboard's actual domain, category, KPI semantics, aliases, units, risk/action group meanings, and display descriptions.
2. **Measured platform data:** dashboard rows, KPI insights, rules, and action records; retain source/provenance when rendered.
3. **Validated graph relationships / causal simulator:** only for causal paths or projected changes that the platform has validated and scoped to the caller's tenant.
4. **Governed runtime policy/formula:** only for a documented, applicable policy with an owner, version, and inputs. No silent universal threshold or inferred contract behavior.
5. **Explicit unavailable state:** if no semantic definition, evidence, validated relationship, or policy exists, report that limitation instead of fabricating a category, risk, root cause, or action.

## Migration risks and safeguards

- **Registry coverage gaps:** missing metadata can make existing dashboard classification less specific. Add a registry completeness check and an explicit unclassified path before deleting fallback taxonomy.
- **Behavior drift:** preserve representative existing-dashboard fixtures while adding logistics and another distinct-domain fixture.
- **False causality:** never turn co-occurring KPI labels into causal edges. Test that absent graph/policy evidence yields no projected effect.
- **Recommendation overreach:** only return platform actions or policy-backed recommendations; verify action provenance and applicability.
- **Presentation changes:** generic report labels may differ from existing UI assumptions. Review serialized report contracts and downstream UI consumers before removing specialized fields.
- **Test fixture bias:** current tests are heavily real-estate-specific. Keep them as regression samples but add independently designed non-real-estate cases and avoid copying current fixed assumptions into new tests.

## Definition of done

- [ ] Registry/dashboard semantic contract is documented and validated against real payloads.
- [ ] Dashboard category and KPI selection are driven by that contract, not hardcoded real-estate taxonomy.
- [ ] No hardcoded real-estate root-cause or risk override can replace evidence-derived results.
- [ ] No domain-specific action is emitted without a source action or applicable configured policy.
- [ ] Financial/causal conclusions are traceable to measured evidence and an approved methodology.
- [ ] Reports render generic KPI metadata and preserve domain wording from the selected dashboard.
- [ ] Logistics and another unrelated-domain end-to-end fixture pass; existing dashboard fixtures remain supported.
- [ ] A final runtime-only search reviews every remaining occurrence of the audited terms and `re_*` identifiers.
