# Migration notes: caller-provided simulation context

The simulation endpoint now requires caller authentication and tenant context in
HTTP headers. Update clients of `POST /api/v1/simulation/simulate` as follows:

- Send the caller token in `Authorization` (for example,
  `Authorization: Bearer <token>`).
- Send the enterprise identifier in `X-Enterprise-Id`.
- Send one or more comma-separated domain identifiers in `X-Domain-Id`.
- Remove `access_token`, `enterprise_id`, `domain_ids`, `domain_id`, and
  `scope_id` from the JSON body. They are no longer part of
  `SimulationRequest`; tenant values must not be sent in the request body.
- Keep simulation inputs such as `query` and optional `dashboard_id` in the
  JSON body.

Requests without Authorization receive `401`. Requests missing either tenant
header, or providing an empty tenant value, receive `400`. Configured server
access tokens are no longer used as a fallback for outgoing request
authentication. The hard-coded enterprise identifier default was also removed.
