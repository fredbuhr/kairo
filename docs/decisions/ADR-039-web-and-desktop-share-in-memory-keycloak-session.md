# ADR-039 — Web and Desktop share an in-memory Keycloak session contract

Status: accepted

Date: 2026-09-09

## Context

KAIRO Core already rejects unauthenticated user requests when `KAIRO_AUTH_ENABLED=true`, but the Cockpit previously issued plain browser requests without propagating the Keycloak bearer token. The live graph stream also used native `EventSource`, which cannot set an Authorization header, and generated News audio was referenced as a raw protected URL.

That mismatch meant the permanent Cockpit could compile while still depending on authentication being disabled in practice.

KAIRO Web and the Tauri wrapper must share one request/authentication contract without persisting long-lived credentials in frontend storage or leaking access tokens into URLs.

## Decision

The shared Cockpit uses the official `keycloak-js` public-client adapter with Authorization Code + PKCE and initializes identity **before React mounts**.

Rules:

1. access and refresh tokens remain in adapter memory; KAIRO does not copy them into LocalStorage, IndexedDB or canonical state;
2. every normal Core request passes through a shared authenticated fetch helper that refreshes a near-expiry token and sends `Authorization: Bearer ...`;
3. the graph activity stream uses authenticated `fetch()` + streamed SSE parsing instead of `EventSource`, so no access token is placed in a query string;
4. protected binary resources such as generated News audio are fetched with the bearer header and exposed to media elements only as short-lived local object URLs;
5. authentication is initialized before the application/router state can consume OIDC callback parameters;
6. logout is explicit and returns through the configured application redirect;
7. the browser and Tauri WebView use the same public Keycloak client contract for the current test slice, with explicit development redirect origins rather than wildcard redirects;
8. `KAIRO_AUTH_ENABLED=false` remains an explicit isolated-development/CI mode only; it must not become an implicit frontend fallback when Keycloak is unavailable.

## Desktop origins

Tauri v2 uses a normal development origin (`http://localhost:5173`) while production custom-protocol origins vary by platform. The local Keycloak realm therefore lists only the known test origins:

- `http://localhost:5173/*`;
- `http://tauri.localhost/*`;
- `tauri://localhost/*`.

Core CORS uses the corresponding explicit origins in the development template.

This embedded WebView OIDC path is sufficient for the current local Test Interface slice. Before distributing KAIRO Desktop broadly, the native login UX should be reviewed against the target platform/OIDC guidance and may move to a system-browser/native adapter without changing the bearer-token API contract used by the Cockpit.

## Consequences

### Positive

- Auth-enabled Core and the real Cockpit are aligned.
- Web and Desktop share one API client and identity display.
- Token refresh is centralized rather than duplicated across workspaces.
- SSE activity remains authenticated without URL token leakage.
- Generated protected media continues working under authentication.
- Authentication failures are visible instead of silently falling back to an insecure mode.

### Trade-offs

- A Keycloak outage now prevents an auth-enabled Cockpit from mounting, by design.
- The streamed SSE parser is slightly more code than native `EventSource`.
- Packaged Desktop OIDC behavior still requires real-platform validation before production distribution.

## Rejected alternatives

### Store tokens in LocalStorage

Rejected because the Keycloak adapter can keep them in memory and persistent browser storage increases token theft/replay exposure.

### Put the token in the SSE/audio URL

Rejected because URLs leak into history, logs, proxies and diagnostics more easily than Authorization headers.

### Disable Core authentication for the Test Interface

Rejected because it would validate the UI against a security model different from the intended product.

### Build a second Desktop API client

Rejected because Desktop is the same Cockpit and should not fork Core request behavior.

## Follow-up

- execute the browser login/API/media/SSE path against the real local Keycloak stack once GitHub runners are available;
- validate packaged Tauri redirects on Windows, macOS and Linux;
- review a system-browser/native OIDC adapter before broad Desktop distribution;
- continue multi-user ownership auditing so an authenticated subject can only observe/mutate its own domain data.
