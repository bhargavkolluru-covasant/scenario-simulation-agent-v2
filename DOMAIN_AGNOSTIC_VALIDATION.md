# Domain-Agnostic Workflow Validation

## Result

**PASS** — the complete LangGraph workflow completed for a logistics demand
increase scenario. The generated executive report contains the expected
logistics-specific outputs and none of the restricted real-estate phrases.

## Input dashboard

- **Name:** Logistics Dashboard
- **Category:** `LOGISTICS`
- **KPIs:**
  - Shipment Volume
  - Fleet Utilization
  - Fuel Cost
  - On-Time Delivery
  - Warehouse Throughput
- **Semantic metadata:** KPI meanings and causes describe shipment volume,
  fleet capacity, delivery service, fuel expenditure, and warehouse throughput.
- **Declared capability mapping:** `shipment_demand_increase` maps to the
  `DEMAND_GROWTH` scenario category and `CAPACITY_PLANNING` strategy.
- No restricted real-estate terms are present in the dashboard semantics.

## Input scenario

> What happens if shipment demand increases by 20% next quarter?

The parser fixture supplies scenario type `shipment_demand_increase`, change
type `increase`, magnitude `20%`, time horizon `next quarter`, and target
entity `Regional Distribution Network`.

## Workflow and output summary

The test invokes the compiled application workflow from its context node
through scenario parsing, dashboard resolution, KPI and semantic selection,
risk and action selection, strategy selection, simulation, impact analysis,
recommendation, explainability, and report generation.

The completed report identifies:

- **Primary KPI:** Shipment Volume
- **Supporting KPI:** Fleet Utilization (also On-Time Delivery)
- **Strategy:** `CAPACITY_PLANNING`
- **Scenario category:** `DEMAND_GROWTH`
- **Primary risk:** Delivery Capacity Risk
- **Secondary risk:** Workforce Capacity Constraints
- **Impact:** Fleet Utilization Impact
- **Recommendation:** Logistics Recommendations, including a capacity
  validation action
- **Report:** successfully generated with a `REP-` report ID

The four required output phrases are asserted in the generated report itself,
not merely in the input dashboard metadata.

## Assertions

- Workflow status is `COMPLETED`, with a generated report and financial model.
- Dashboard category, scenario category, and capability-mapped strategy match
  the logistics metadata.
- Selected primary and supporting KPIs, and the primary and secondary risks,
  match the scenario evidence.
- The generated report contains:
  - `Delivery Capacity Risk`
  - `Fleet Utilization Impact`
  - `Workforce Capacity Constraints`
  - `Logistics Recommendations`
- Generated report, simulation, impact, recommendation, and financial outputs
  do not contain `GDV`, `HBU`, `handover`, `hurdle`, `construction`, or
  `project delivery`.

## Pass/fail and reproducibility

- **PASS**
- Command:
  `python -m pytest app/tests/test_workflow_e2e.py::test_logistics_demand_increase_runs_domain_agnostic_workflow -q`
- Result: **1 passed**

Dashboard/platform clients, parser, and LLM responses use deterministic test
doubles. The full in-process workflow graph and report generation run normally;
this validates workflow behavior against the supplied logistics semantics,
not connectivity or response quality of live external services.
