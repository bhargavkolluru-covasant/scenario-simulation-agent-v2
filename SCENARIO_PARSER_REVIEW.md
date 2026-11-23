# Scenario Parser Review

## Previous parser behavior

- Used a deterministic regex fallback when the LLM was unavailable or failed.
- Filled missing fields with generic values such as `enterprise_scenario`,
  `scenario_change`, `0%`, and `Unknown Entity`.
- Returned guessed scenarios instead of asking for clarification.
- Relied on output defaults that allowed incomplete structured results to pass
  validation.

## New parser behavior

- Structured LLM output is the only parsing source.
- The result is validated with `ParsedScenario` before being returned.
- `scenario_type`, `change_type`, `change_percentage`, `time_horizon`, and
  `target_entity` are required; placeholder values and zero-change defaults are
  rejected.
- Unavailable structured parsing or incomplete/invalid output raises
  `ScenarioClarificationError` with:

  > I couldn't understand the business change being requested. Please rephrase the scenario.

- No keyword or regex fallback constructs a scenario.

## Edge cases fixed

- "follow up" is explicitly treated as an action, not an increase.
- "below forecast" maps to a decrease only when paired with an explicit
  percentage.
- Missing change magnitude, target, type, category, or time-horizon field is
  rejected instead of defaulted.
- Empty input and an unconfigured structured parser request clarification.

## Tests added or updated

- Added structured-output acceptance cases for all five requested pass examples.
- Added clarification cases for all four requested ambiguous examples.
- Added validation coverage for each required field, placeholder values, zero
  change, and unavailable structured parsing.
- Updated parser-node and offline-parser tests to verify that no heuristic
  fallback is used.

## Files changed

- `app/models/scenario_models.py`
- `app/services/scenario_parser_service.py`
- `app/tests/test_new_components.py`
- `app/tests/test_scenario_parser.py`
- `app/tests/test_workflow_resiliency.py` (complete parsed-scenario fixture)

Validation: **162 passed, 18 skipped** using the offline pytest configuration.
