# Nevolium Core

Canonical HTTP/API and policy boundary.

The current foundation intentionally exposes only health/architecture/component-registry endpoints. Block 1 adds migrations, canonical entities, transactional outbox, authorization and audit.

Core must never become an arbitrary agent-execution process; long-running AI/tool work belongs to Temporal workers.
