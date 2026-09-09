# ADR-026 — Capability results project into canonical Conversations

Status: Accepted

Date: 2026-09-09

## Context

The Command Kernel already persists the user's message and the route to a durable capability Task. News and Autonomous Research, however, complete asynchronously and store their rich output as canonical Artifacts. Without a final assistant message, a KAIRO Conversation contains only the user's side of the exchange and the Web UI must reconstruct dialogue from capability-specific polling state.

Duplicating the entire Artifact into the conversation would create two competing canonical copies of sourced reports, tool provenance and structured metadata. Not writing anything would prevent conversation history and memory projections from representing what KAIRO actually answered.

## Decision

When a Command-owned final capability Task reaches canonical completion, Core appends exactly one deterministic `ConversationMessage(role="assistant")`.

The message ID is derived from the Command ID and a stable projection version. Completion retry therefore repairs or returns the same message instead of duplicating chat history.

The assistant message contains only a compact human-facing projection:

- `news.brief` projects its final summary;
- `research.autonomous` projects `report.answer`.

Its metadata contains stable references to the Command, capability, Task, WorkflowExecution, Artifact and execution status. The rich Artifact remains the authoritative structured result and retains sources, findings, MCP invocation IDs, market-impact data and any other specialist output.

The Command result JSON records the Artifact and assistant-message IDs, but the Command remains `accepted`: that status describes the authoritative route. Final capability state is recorded separately as `execution_status=completed`.

When a Command-owned final capability Task fails terminally, Core marks the Command `failed` and appends one deterministic assistant failure message. The user-visible message is intentionally generic and does not leak the raw Worker/provider error into conversational memory. The technical error remains available in canonical Command/execution state and audit logs.

Semantic routing Tasks also contain a Command ID, but they are implementation Tasks rather than the Command's final capability Task. Projection only applies when `Command.task_id` equals the completed/failed Task ID, so routing-workflow outcomes cannot masquerade as assistant answers.

Because `ConversationMessage` is inserted through the ORM, the existing same-transaction memory projection event is emitted automatically. Derived Mem0/Graphiti projections can therefore learn from KAIRO's final answers without treating Artifacts or NATS as canonical conversation state.

## Consequences

- KAIRO's canonical Conversation becomes a complete user/assistant history.
- Capability-specific Artifacts stay authoritative and are not duplicated wholesale.
- Retry of completion/failure is idempotent at the chat layer.
- Final failures become visible in both Command and Conversation state.
- Conversation memory projections receive assistant answers through the same event path as user messages.
- Future capabilities must define a small result renderer before they can project an assistant message; they should not serialize arbitrary Artifact JSON into chat by default.
