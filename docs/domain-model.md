# Nevolium canonical domain model

Nevolium's domain graph is the common language between chat, projects, Gantt, mindmaps, knowledge, automations, agents, finance and devices.

PostgreSQL stores the canonical entities and relationships. Graph views, Graphiti context, vector indexes and UI hierarchies are projections over that state.

## Universal identity

Every durable entity has:

- stable UUID/ULID-style identifier;
- `type`;
- `created_at` / `updated_at`;
- optional lifecycle state;
- actor/provenance metadata;
- optional project/portfolio scope;
- soft-delete/archive semantics where appropriate.

## Work and planning

### Portfolio / Project / Workstream
Organize durable bodies of work without forcing every relationship into a folder hierarchy.

### Objective / Milestone / Task
Tasks support owner, status, priority, estimate, deadline, dependencies, schedule, authority ceiling, budget, automation links and resulting artefacts.

### Plan / Schedule
A plan is a versioned scheduling object. Gantt is one view of it, not a separate data silo.

Dependencies are first-class edges so rescheduling and critical-path calculations can be implemented in Nevolium rather than being trapped inside a Gantt widget.

## Knowledge and thinking

### Idea
A proposal that is explicitly not yet a decision.

### Decision
A committed choice with rationale, alternatives, evidence, consequences and supersession links.

### Note / Document / Source / Asset
Human-authored or imported content and its binary artefacts.

### KnowledgeClaim
A claim with epistemic status:

- `fact`;
- `hypothesis`;
- `deduction`;
- `opinion`;
- `unknown`.

Claims support provenance, confidence, verification date and sources.

### GraphNode / Relationship
Domain entities can appear as graph nodes without duplicating their identity. Relationships are typed, directed/undirected as required and carry temporal/provenance metadata.

The 2D mindmap, 3D mindmap and knowledge graph therefore visualize the same Nevolium world model through different projections.

## People and communication

### Person / Organization
Contacts, collaborators, companies and relationship context.

### Conversation / Message / Thread
Unified communication records with source adapter metadata. External systems remain the authoritative delivery service; Nevolium stores normalized references and user-owned context.

### CalendarEvent
Time-bound event linked to people, projects, tasks, locations and source calendars.

### Notification / AttentionItem
A normalized event that may require user attention. Attention items can be generated from emails, approvals, workflows, finance alerts or system health.

## AI and automation

### Agent
Named specialization with model policy, skill/tool set, memory scope and authority ceiling.

### Skill / Tool / Integration
Capabilities available through MCP, native adapters or Activepieces.

### Automation
A standing rule/trigger definition owned by Nevolium even when execution is delegated to Activepieces or Temporal.

### WorkflowRun / ActivityRun
User-visible durable execution correlation. Temporal owns low-level runtime state; Nevolium stores purpose, policy, cost, approvals, status projection and result references.

### ApprovalRequest
Captures the action being proposed, actor, required authority, risk summary, exact side effect, expiry and approval/rejection evidence.

### ModelRequest / UsageRecord
Tracks logical model route, provider/model chosen, tokens, latency, cost, cache, quality/evaluation and originating workflow/entity.

## Devices and environment

### Device
Registered desktop, phone, server, browser session or trusted hardware endpoint.

### DeviceCapabilityGrant
User-approved capability such as microphone, clipboard, selected directories, screenshots or command execution.

### HomeEntity
Normalized reference to a Home Assistant entity/device/automation without copying Home Assistant's entire state model into Nevolium.

### Location / Place
Reusable place linked to calendar events, people, projects and maps.

## Finance and crypto

### FinancialAccount
Fiat/bank/budget/investment account reference.

### Wallet
Blockchain wallet/address metadata. Raw private keys and seed phrases are never Nevolium domain fields.

### Holding / Position
Normalized asset quantity/exposure with source and valuation metadata.

### LedgerEntry / TransactionReference
Imported financial or blockchain transaction reference.

### TransactionProposal
An unsigned proposed action containing exact chain/exchange/account, amount, destination, fee/price constraints, simulation result, risk assessment, policy decision and expiry.

### ExecutionAuthorization
Explicit evidence that a financial action may proceed. The signer remains isolated from the LLM/agent runtime.

## Audit and security

### Policy / PermissionGrant
Defines allowed capabilities and ceilings by user, agent, device, integration and project scope.

### AuditEvent
Append-oriented record of security-relevant or autonomous actions.

### SecretReference
Opaque reference to OpenBao; secret material is never stored in ordinary domain rows.

## Relationship examples

```text
PROJECT contains TASK
TASK depends_on TASK
TASK scheduled_in PLAN
TASK assigned_to PERSON|AGENT
DECISION resolves IDEA
KNOWLEDGE_CLAIM supported_by SOURCE
CONVERSATION concerns PROJECT
CALENDAR_EVENT involves PERSON
WORKFLOW_RUN executes TASK
WORKFLOW_RUN produces ASSET
AGENT uses SKILL
DEVICE has_capability DEVICE_CAPABILITY_GRANT
WALLET contains HOLDING
TRANSACTION_PROPOSAL affects WALLET
APPROVAL_REQUEST authorizes TRANSACTION_PROPOSAL
HOME_ENTITY related_to LOCATION
```

## Data invariants

- an idea is not a decision;
- a deduction is not a fact;
- Graphiti/Mem0/vector indexes are never the only copy of canonical facts or decisions;
- every external side effect has an idempotency/correlation key where technically possible;
- autonomous tasks carry an authority ceiling before execution;
- important generated conclusions retain provenance to models, tools and sources;
- financial signing material never enters an LLM context;
- archiving does not silently erase audit history.
