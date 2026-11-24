# Scenario and Strategy Refactor

## Summary

Scenario intent no longer scans query text for business keywords or selects a
default operational category. It preserves structured parser fields and uses
explicit scenario context or dashboard capability mappings for intent,
category, and themes. Missing mappings produce `UNCLASSIFIED`.

Strategy selection no longer routes by dashboard category, scenario category,
query text, or domain-specific terms. It accepts an explicit strategy in
scenario context/semantics or resolves the parsed `scenario_type` through
dashboard capabilities. Missing or unsupported mappings produce
`UNCLASSIFIED`; no generic strategy is guessed.

## Capability contract

Mappings are read from `dashboard_context.capabilities` or
`dashboard_context.dashboard_semantics.capabilities`:

```json
{
  "scenario_intent_map": {
    "population_growth": {
      "scenario_category": "DEMAND_GROWTH",
      "intent_type": "DEMAND_GROWTH",
      "themes": ["demand"]
    }
  },
  "scenario_strategy_map": {
    "population_growth": {
      "strategy": "DEMAND_GROWTH",
      "methodology": ["Declared capability methodology"]
    }
  }
}
```

Mapping keys are exact parsed scenario types (case and separator normalized;
no substring matching). Strategy values must match a supported
`SimulationStrategy`. `methodology` is optional and is returned only when
declared by the capability.

The tests cover retail population growth, logistics shipment increase, finance
cash-flow change, and real-estate project delay. They also verify that legacy
domain terms and `LAND_FEASIBILITY` alone do not classify a scenario or select
a strategy.

## Scope

Updated `scenario_intent_service.py` and `strategy_selector_node.py`, with
focused test updates. Dashboard intelligence, report generation, recommendation
logic, and the simulation engine were not modified.
