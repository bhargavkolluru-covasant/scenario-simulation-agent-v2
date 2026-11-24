# Configuration Audit Report

## Runtime configuration inventory

| Variable | Referenced file(s) | Usage |
|---|---|---|
| `API_TIMEOUT` | `app/config/settings.py`, `app/clients/*.py`, `app/services/rule_compilation_service.py` | HTTP client timeout; startup requires a positive finite value. |
| `PLATFORM_BACKEND_URL` | `app/config/settings.py`, `app/clients/dashboard_client.py`, `app/clients/knowledge_graph_client.py`, `app/clients/rules_client.py` | Required default URL for platform service clients; startup validates an absolute HTTP(S) URL. |
| `DASHBOARD_URL` | `app/config/settings.py`, `app/clients/dashboard_client.py` | Optional dashboard service override. |
| `KPI_INSIGHTS_URL` | `app/config/settings.py`, `app/clients/kpi_insights_client.py` | Optional KPI insights service override. |
| `ACTIONS_URL` | `app/config/settings.py`, `app/clients/actions_client.py` | Optional actions service override. |
| `DASHBOARD_ID` | `app/config/settings.py`, `app/api/routes.py`, `app/nodes/dashboard_node.py` | Optional default dashboard selection. |
| `ARIIA_ENTERPRISE_ID` | `app/config/settings.py`, `app/nodes/context_node.py`, `app/services/context_service.py`, `app/clients/base_client.py` | Optional legacy/direct-workflow tenant fallback; API requests use tenant headers. |
| `ARIIA_DOMAIN_IDS` | `app/config/settings.py`, `app/nodes/context_node.py`, `app/services/context_service.py`, `app/clients/base_client.py` | Optional legacy/direct-workflow domain fallback; empty by default. |
| `ARIIA_COOKIE` | `app/config/settings.py`, `app/clients/base_client.py` | Optional platform session cookie. |
| `ARIIA_SESSION_ID` | `app/config/settings.py`, `app/clients/base_client.py` | Optional platform session header. |
| `SEMANTIC_REGISTRY_URL` | `app/config/settings.py`, `app/clients/semantic_registry_client.py` | Optional semantic registry URL override. |
| `KNOWLEDGE_GRAPH_URL` | `app/config/settings.py`, `app/clients/knowledge_graph_client.py` | Optional knowledge graph URL override. |
| `RULES_SERVICE_URL` | `app/config/settings.py`, `app/clients/rules_client.py`, `app/services/rule_compilation_service.py` | Optional rules URL and rule-compilation fallback. |
| `RULE_COMPILATION_URL` | `app/config/settings.py`, `app/services/rule_compilation_service.py` | Optional rule-compilation URL override. |
| `VENDOR_SERVICE_URL` | `app/config/settings.py`, `app/clients/vendor_client.py` | Optional vendor service URL override. |
| `PROCUREMENT_SERVICE_URL` | `app/config/settings.py`, `app/clients/procurement_client.py` | Optional procurement service URL override. |
| `INVOICE_SERVICE_URL` | `app/config/settings.py`, `app/clients/invoice_client.py` | Optional invoice service URL override. |
| `EXPENSE_SERVICE_URL` | `app/config/settings.py`, `app/clients/expense_client.py` | Optional expense service URL override. |
| `MARKET_RISK_SERVICE_URL` | `app/config/settings.py`, `app/clients/market_risk_client.py` | Optional market-risk service URL override. |
| `ARIIA_ACCESS_TOKEN` | `app/config/settings.py`, `app/tests/test_authentication.py`, `app/tests/test_postman_equivalence.py`, `app/tests/test_token_diagnostics.py`, `app/tests/kg_validation_support.py`, `scripts/test_auth_debug.py`, `scripts/test_token_current.py` | Optional manual/integration-test credential. Request execution uses the caller token, not this setting. |
| `ARIIA_SCOPE_ID` | `app/config/settings.py`, `app/api/routes.py`, `app/nodes/context_node.py`, `app/services/auth_service.py`, `app/clients/base_client.py` | Optional scope compatibility context. |
| `ARIIA_SCOPE_HEADER_NAME` | `app/config/settings.py`, `app/services/auth_service.py`, `app/clients/base_client.py` | Configures the optional scope header name. |
| `GROQ_API_KEY` | `app/config/settings.py`, `app/services/groq_service.py`, `app/services/llm_gateway.py`, `app/main.py` | Required Groq credential; validated before application startup. |
| `GROQ_MODEL` | `app/config/settings.py`, `app/services/groq_service.py` | Groq model selection; must be non-empty. |

Tenant context is request-scoped for the API: `app/api/routes.py` requires
`X-Enterprise-Id` and `X-Domain-Id` on each simulation request. These headers
are not required as static startup settings.

## Test-only environment variables

| Variable | Referenced file(s) | Usage |
|---|---|---|
| `RUN_KG_VALIDATION` | `app/tests/kg_validation_support.py` | Enables opt-in live knowledge-graph tests. |
| `KG_NODE_ID` | `app/tests/kg_validation_support.py` | Node identifier for live graph validation. |
| `KG_NODE_TYPE` | `app/tests/kg_validation_support.py` | Node type for live graph validation. |
| `RUN_ARIIA_MANUAL_TEST` | `app/tests/test_postman_equivalence.py` | Enables an opt-in live API equivalence test. |

## Removed configuration

| Variable or entry | Previously referenced in | Removal reason |
|---|---|---|
| `BASE_URL` | `app/config/settings.py`, local `.env` | Its value was shadowed by the always-configured platform URL and no client selected it directly; service resolution now requires `PLATFORM_BACKEND_URL`. |
| `COPILOT_BASE_URL` | Local `.env` only | Deprecated provider configuration; no runtime provider consumes it. |
| `COPILOT_MAX_RETRIES` | Local `.env` only | Deprecated provider configuration; no runtime provider consumes it. |
| `COPILOT_MODEL` | Local `.env` only | Deprecated provider configuration; no runtime provider consumes it. |
| `COPILOT_TIMEOUT` | Local `.env` only | Deprecated provider configuration; no runtime provider consumes it. |
| `GEMINI_API_KEY` | Local `.env` only | Deprecated provider credential; no runtime provider consumes it. |
| `GEMINI_MODEL` | Local `.env` only | Deprecated provider configuration; no runtime provider consumes it. |
| `LLM_PROVIDER` | Local `.env` only | Provider selection is no longer configurable; Groq is the sole provider. |
| Explicit lowercase `os.getenv` aliases for ARIIA token, scope, and domain settings | `app/config/settings.py` | Redundant with `BaseSettings` environment loading; direct duplicate lookups were removed. |

Copilot/Gemini provider variables are absent from application settings and the
new `.env.example`. The checked-in `COPILOT_GEMINI_REMOVAL_REPORT.md` is
historical documentation, not active configuration.
