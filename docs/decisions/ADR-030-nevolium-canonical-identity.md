# ADR-030 — Nevolium is the canonical project identity

- Status: accepted
- Date: 2026-09-11

## Context

The project was still using a temporary working identity across its public name and technical
namespaces. No user deployment, production database, durable workflow, identity realm or backup had
been created yet. Keeping parallel names during the first pilot would create avoidable ambiguity in
configuration, support and recovery procedures.

## Decision

Nevolium is the single canonical identity for the product and repository going forward.

- Human-facing text uses `Nevolium`.
- Environment variables and constants use the `NEVOLIUM_` prefix.
- Python distributions/modules use `nevolium-*` and `nevolium_*`.
- JavaScript workspace packages use the `@nevolium/*` scope.
- Runtime identities use `nevolium` for Compose, services, databases, roles, object prefixes,
  Temporal queues, NATS subjects, authentication and secret paths.
- Protocol names owned by the product use `Nevolium` in HTTP and event headers.
- The current tracked tree must contain no reference to the temporary identity. CI enforces both
  content and path checks and asserts the main canonical identifiers.

There is no compatibility alias or dual-read period. The first server installation must start from
fresh Nevolium databases, volumes, streams, workflows, realm and secret namespace.

## Historical evidence

Git commit identifiers, workflow run identifiers and measurement results remain unchanged. Archived
textual labels and repository links are normalized to the canonical identity in the current tree;
the exact pre-transition evidence remains recoverable from commit
`8cc34c964d34c360fe9b42e50e2ac9daca678a75`. Git history must not be rewritten for branding.

## Consequences

- Existing development configuration files must be recreated from the Nevolium templates.
- Any installation containing real data would require a dedicated migration before adopting this
  decision; none exists at the time of acceptance.
- All D04 validation must run again on the renamed head. Earlier green runs remain useful evidence
  for their exact commits but do not qualify the Nevolium runtime.
- The GitHub repository and active metadata must be renamed after the code is green. Historical
  commits, closed pull requests and workflow logs are retained as history.
