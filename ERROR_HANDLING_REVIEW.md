# API Error Handling Review

## Files changed

- `app/api/routes.py`
- `app/clients/base_client.py`
- `app/tests/test_runtime_request_context.py`
- `REVIEW_REMEDIATION_PLAN.md`
- `ERROR_HANDLING_REVIEW.md`

## Security improvement

Simulation execution failures now return a generic detail and a UUID request
ID. Ordinary exceptions retain HTTP 500; an `HTTPException` raised during
workflow execution retains its status code but uses the same generic response.
The exception and request ID remain in server logs through the existing
`logger.exception` call; exception text is no longer interpolated into the
client response.

Exception strings stored in workflow state are redacted at the API boundary,
including nested `error` fields. Failed report-generation output is also
redacted without changing the report-generation node. Failed BaseClient GET
and POST logs retain the upstream status code but no longer log the response
body.

## Repository search findings

- `str(exc)` was used in the simulation route's HTTP 500 detail; this direct
  leak is fixed.
- Nodes store exception text under `error` in workflow state/results:
  `context_node.py`, `compile_rule_node.py`, `impact_analysis_node.py`,
  `simulation_node.py`, and `report_generation_node.py`. The simulation API
  redacts those fields in returned state and report data.
- `token_service.py` stores exception text in diagnostic `raw_payload.error`;
  recursive API error-field redaction covers it if that metadata reaches
  returned workflow state.
- `response.text` was logged in `BaseClient` HTTP status failures; those logs
  now include the status code only. `get_with_status` and `post_with_status`
  still return parsed content or text to internal callers. Current repository
  call sites are diagnostics/tests, not the simulation API response path.
- Other `response.text` hits are manual diagnostic tests that print responses.
- No `repr(exc)` or `traceback` matches were found in Python source.
- Existing `logger.exception` calls were retained.

## Before / after

Before, an upstream failure could produce a client response containing an
exception message, URL, or other internal details:

```json
{
  "detail": "Simulation execution failed: ConnectError('https://internal.example/...')"
}
```

After, the response keeps the existing 500 status and exposes only a generic
message and a correlation ID:

```json
{
  "detail": "We couldn't run this simulation right now. Please try again.",
  "request_id": "<uuid>"
}
```
