# Platform acceptance scenarios

These scenarios replace the old OpenClaw-specific V0 acceptance tests.

## AT-P01 — Canonical state survives projections
Create a project, decision, task, document and relationship; rebuild vector/Graphiti/Mem0 projections; canonical records and relationships remain unchanged.

## AT-P02 — Durable approved workflow
Start a multi-step Temporal workflow, disconnect all clients, restart the worker during an idempotent activity, and confirm the workflow resumes without duplicating a side effect.

## AT-P03 — Authority denial
Give an agent technical access to an external tool but no policy grant. The action is denied before the side effect and an approval request can be created.

## AT-P04 — Cost ceiling
Run an AI workflow with a hard USD/token budget and confirm routing/accounting stops or escalates before exceeding policy.

## AT-P05 — 2D/3D graph identity
Edit a relationship in the 2D mindmap, observe it in 3D and project drill-down without creating duplicate entities.

## AT-P06 — Gantt round trip
Move a task in the Gantt; dependencies and canonical schedule update; an AI replan can produce a proposed plan version without overwriting the accepted plan until approval.

## AT-P07 — Realtime multi-device
Edit a shared document/mindmap on two clients via Yjs, persist the result and reconnect after server/client restart without losing canonical content.

## AT-P08 — Crypto signing isolation
Prepare/simulate a transaction proposal through an agent. Confirm no private key is available in LiteLLM, Langfuse, Mem0, Graphiti or worker environment; signing requires the isolated signer/user interaction.

## AT-P09 — Backup restore
Restore PostgreSQL, object storage and required configuration into a clean environment and rebuild derived indexes successfully.

## AT-P10 — Specialist-engine replacement
Swap or disable one projection/adapter in a test environment (for example Mem0 or the Gantt renderer) without changing canonical domain records or public API contracts.
