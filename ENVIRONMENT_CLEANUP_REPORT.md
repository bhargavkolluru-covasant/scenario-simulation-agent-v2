# Environment and Configuration Cleanup Report

## Files changed

- `app/config/settings.py`
- `app/main.py`
- `app/tests/conftest.py`
- `app/tests/test_llm_gateway.py`
- `app/tests/test_settings_validation.py`
- `.env.example` (new)
- `README.md`
- Local ignored `.env` (obsolete keys removed; secret values were not inspected
  or included in this report)
- `CONFIG_AUDIT_REPORT.md` (new)
- `ENVIRONMENT_CLEANUP_REPORT.md` (new)

## Removed variables and entries

- Removed `BASE_URL`, which was an unreachable fallback behind the default
  `PLATFORM_BACKEND_URL`.
- Removed `COPILOT_BASE_URL`, `COPILOT_MAX_RETRIES`, `COPILOT_MODEL`, and
  `COPILOT_TIMEOUT` from the local `.env`.
- Removed `GEMINI_API_KEY` and `GEMINI_MODEL` from the local `.env`.
- Removed `LLM_PROVIDER`; Groq is the only supported provider.
- Removed redundant explicit lowercase environment lookups from settings.
- Removed the hardcoded default domain list. Domain context is caller-provided
  for API requests and no longer silently defaults to a static value.

## Startup validation

Application lifespan now validates configuration before serving requests:

- `GROQ_API_KEY` must be non-empty.
- `PLATFORM_BACKEND_URL` must be configured and be an absolute HTTP(S) URL.
- Any configured service URL override must be an absolute HTTP(S) URL.
- `API_TIMEOUT` must be finite and positive.
- `GROQ_MODEL` must be non-empty.

Errors identify the missing or invalid variable without echoing credential
values. Enterprise/domain context remains request-scoped and is checked by the
simulation endpoint, preserving the existing tenant-header contract.

## Before/after inventory

| Inventory | Before | After |
|---|---:|---:|
| Settings fields | 25, including dead `BASE_URL` | 24; `PLATFORM_BACKEND_URL` is explicit and required at startup |
| `.env.example` | Missing | 23 documented application variables |
| Copilot/Gemini/provider-selection keys in local `.env` | 7 | 0 |
| Hardcoded default domain IDs | Present | Removed; empty unless explicitly configured |

The local `.env` is ignored by Git. It was edited without printing or recording
its values. `ARIIA_ACCESS_TOKEN` remains an optional manual/integration-test
setting and is not used as the API caller token.

## Tests

- Missing `GROQ_API_KEY` makes application startup fail with a clear message.
- Missing `PLATFORM_BACKEND_URL` makes application startup fail with a clear
  message.
- Invalid service URL and non-positive timeout configurations fail at startup.
- The Groq health/startup test supplies valid test configuration and remains
  independent of local environment values.
- A test-only platform URL fixture keeps offline client tests independent of
  developer-specific `.env` files.

Validation: full offline suite **180 passed, 18 skipped**; focused configuration
and request-context tests **22 passed, 1 skipped**.
