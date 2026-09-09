# KAIRO Test Interface v1

Status: implementation contract for the first daily-use KAIRO interface.

This document freezes the architecture of the interface that replaces the earlier technical prototype. The goal is not to build a disposable UI and redesign it later. The first test interface is the product interface: later work may tune rendering, spacing, motion and information density, but should extend these boundaries rather than replace them.

## Product premise

KAIRO is not a dashboard, chatbot wrapper or decorative mind map.

Its main visual surfaces are navigable representations of KAIRO's canonical world model: projects, tasks, documents, conversations, agents, approvals, artefacts and other durable entities are nodes; known relationships are connections.

The mycelium and 2D Brain map are functional UI. Decorative motion may exist, but a visible semantic relationship must correspond to a real KAIRO relationship or an explicitly identified projection/provenance class.

## Stable shell

The desktop layout has three coordinated surfaces:

1. **Primary navigation** — a restrained left rail for durable product areas.
2. **Working surface** — Home/KAIRO Brain or a specialist operational workspace.
3. **Context rail** — a right-side contextual surface that appears only when useful.

A compact KAIRO command dock is always available but never dominates the product. Long conversations may expand into a panel without turning Home into a chat application.

### Primary navigation

Durable product areas:

- Home
- Assistant
- Projects
- Knowledge
- KAIRO Brain
- Tasks
- Calendar
- Agents
- Automations
- Finance & Crypto
- Tools
- Settings

Availability is capability-driven. Unimplemented or disabled specialist areas should be hidden or explicitly unavailable rather than populated with fake content.

### Specialist workspaces

Specialist workspaces do not create a second application shell. Projects, Tasks, Knowledge, Calendar, Gantt, Agents, Automations, Tools, Finance and later areas occupy the same central product while preserving primary navigation, universal search, command dock, assistant access and KAIRO identity.

A specialist workspace must use canonical KAIRO APIs or explicitly identified derived/sourced read models. It must not introduce its own authoritative project/task/document state merely because a tabular, timeline or form-oriented view is more convenient than the mycelium.

When a specialist view exposes an entity already represented spatially, it should provide a direct path back to that same canonical entity in KAIRO Brain. Creation or mutation in a specialist workspace must invalidate/update the shared graph projection so the world model and operational view converge without manual synchronization.

Operational depth may grow incrementally, but every active control must affect a real capability. A visually complete fake workspace is worse than an explicit unavailable state.

### Context rail

The rail is composed from contextual sections, not a fixed dashboard:

- selected entity details
- attention and approvals
- running agents/workflows
- Today
- recent activity
- project state
- finance snapshot when the finance profile is active

The rail must be collapsible and may disappear when nothing requires it.

## One canonical graph, multiple renderers

Home and KAIRO Brain use the same graph contract. There must not be a decorative Home graph and a second independent “real” graph later.

KAIRO Brain may render the current projection in three forms:

- **3D mycelium** for spatial exploration;
- **2D mind map** for dense inspection and branch navigation;
- **accessible list/tree-like view** for linear and assistive use.

All three consume the same filtered `KairoGraphProjection`. Switching renderer must not create synchronization work or change canonical state.

The engine is renderer-independent at the data/layout boundary:

- KAIRO Core decides which canonical entities and relationships are relevant;
- `@kairo/graph` defines the client graph contract and pure presentation projections;
- the 3D layout worker computes stable spatial positions;
- React Three Fiber / Three.js renders the mycelium;
- the 2D renderer computes a deterministic presentation-only radial layout;
- accessible views consume the same node/edge identities.

ADR-033 defines the 2D mind-map boundary: its temporary tree parent, depth, angle and dragged coordinates are presentation state only. All semantic edges retain Core provenance.

## Canonical graph projection

PostgreSQL remains authoritative. Graphiti/Neo4j and Mem0 are derived projections and cannot silently become the source of product relationships.

The spatial UI consumes KAIRO-owned read models:

- `GET /v1/graph/home`
- `GET /v1/graph/neighborhood/{entity_type}/{entity_id}`
- `GET /v1/graph/search`

The read model may derive display-oriented properties such as importance, recency, relationship degree, cluster hints and level-of-detail. These values are presentation projections, not new canonical facts.

The read model may also expose canonical foreign-key relationships such as Task → Project. These are valid graph connections even without a separate `relationships` row because the underlying linkage is canonical. Explicit `relationships` rows and FK-derived structure remain visually/provenance-distinguishable.

## KAIRO system anchor

The KAIRO symbol may appear as a spatial anchor in the global view.

It is a UI/system anchor, not a fake domain entity. User data must never be fabricated merely to make the scene visually richer. Empty accounts therefore show the KAIRO anchor and onboarding actions rather than synthetic projects or connections.

## Spatial and Brain behavior

The final test renderer family must support:

- hover
- selection
- contextual focus
- semantic zoom in 3D
- limited orbit/rotation in 3D
- pan/zoom in 2D
- branch isolation
- search → focus
- navigation history and recenter
- type/relation filtering
- deterministic/stable layout seeding
- organic node appearance in 3D
- activity pulses from real KAIRO events
- reduced-motion mode
- adaptive 3D quality modes
- 2D mind-map projection
- accessible non-3D projection

### Semantic zoom

Camera distance alone is not enough. The visible information changes with conceptual depth.

- global: dominant projects/contexts and urgent attention
- intermediate: real projects, tasks, documents, conversations and active actors
- close: secondary objects and explicit relationships
- detail: relationship explanations, provenance and satellites

The server limits the projection; renderers apply visual LOD. A large account must not send or render every entity at once.

## Mycelium visual language

Connections should feel organic rather than diagrammatic:

- curved splines
- irregular branching
- variable thickness and luminosity
- restrained cyan/turquoise/green bioluminescence
- very limited violet accents
- slow motion
- subtle depth, parallax and occlusion
- no aggressive cyberpunk, gaming HUD or crypto-cliché styling

Clusters must read as local density/gravity, not enclosing category bubbles. Sparse light wisps or shared filament density are preferred to visible containers around groups.

Motion should communicate life and activity without increasing cognitive load.

The 2D map should inherit the same quiet visual identity while remaining recognizably diagrammatic enough for fast reading. Explicit canonical relationships and canonical FK structure must remain distinguishable without relying only on color.

## Interaction contract

### Hover

The hovered node becomes slightly clearer. Direct relationships gain salience and unrelated content recedes. A compact label may show entity type, role/context and recent activity.

### Click

Selects the node, stabilizes its immediate neighborhood and drives the context rail.

### Double click / Explore

Focuses the selected entity and requests its canonical neighborhood projection. Double click is a desktop shortcut; an explicit Explore action must exist for touch and accessibility.

In the 2D map, dragging changes local layout only. It does not edit a relationship or create domain state.

### Natural-language navigation

Assistant requests may return typed UI focus/highlight directives. A model never receives direct Three.js or React Flow authority. The frontend validates and applies KAIRO-owned UI directives.

## Human work planning

Tasks, Today, Gantt and the KAIRO Calendar are alternate views over the same explicit Task planning fields. They do not infer hidden urgency or maintain separate planning databases.

Capability execution Tasks belong to Agents/Activity semantics rather than the human planning surface even though both are stored canonically as Tasks. ADR-030 and ADR-031 define these boundaries.

## External calendar provenance

External calendars are context, not automatic KAIRO work state.

KAIRO may ingest normalized provider snapshots into `CalendarSource` and `ExternalCalendarEvent` records. The Calendar workspace overlays these snapshots on KAIRO Task planning while always retaining source/provider identity.

Rules:

- KAIRO Task planning remains KAIRO-owned canonical work state;
- an external event does not silently become a Task, Project or Relationship;
- source/event identity and provider update/observation metadata remain available;
- provider/OAuth credentials are never stored in event snapshot rows;
- trusted connectors normalize provider data through an internal Core ingestion boundary;
- provider deletion/reschedule can update the sourced snapshot without mutating KAIRO work;
- explicit conversion into a KAIRO Task, if added later, requires an audited KAIRO mutation.

ADR-034 defines this boundary.

## Automations and external workflow execution

KAIRO owns Automation definitions, authority and invocation history. Activepieces is an execution adapter, not a second authoritative product surface.

Rules:

- new Automation definitions start disabled;
- webhook endpoints remain behind OpenBao SecretReferences rather than frontend/domain rows;
- KAIRO constructs the fixed internal Activepieces origin and does not accept arbitrary secret-supplied destination URLs;
- each invocation creates a canonical capability Task/WorkflowExecution and passes through the normal policy/approval boundary;
- webhook execution is not blindly retried after a possible side-effect boundary;
- a lost/ambiguous response is recorded explicitly for reconciliation instead of being silently replayed;
- response evidence is bounded by default rather than importing arbitrary downstream response bodies into canonical state.

ADR-035 defines this boundary.

## Finance and Crypto provenance / custody boundary

Finance & Crypto is an operational view over sourced financial observations, not a wallet custody surface.

KAIRO Core owns normalized `FinanceSource`, `FinanceAccount` and `FinancePosition` observations. Replaceable connectors such as Rotki, exchanges, wallets or future banking adapters feed a trusted snapshot boundary. Provider identity and observation time remain explicit.

Rules:

- no fake holdings are shown when no source has provided a position;
- a sourced position is an observation, not a current spend-authority guarantee;
- public wallet addresses may be stored as provenance; private keys, seeds, mnemonics and provider credentials may not enter Finance snapshot/proposal JSON;
- source keys cannot silently rebind to another external account;
- full source snapshots may remove stale observations without creating transactions;
- KAIRO may prepare an unsigned transaction proposal only for an asset observed on the selected account;
- Test Interface v1 exposes no sign/send/broadcast action;
- any future signing requires the policy/approval boundary plus an isolated signer, hardware wallet or explicit user-wallet interaction;
- LLM/agent processes never receive private keys or seed phrases.

The first concrete provider adapter is Rotki and it obeys additional rules:

- `FinanceConnector` records are KAIRO-owned, Project/owner scoped and created disabled;
- Rotki username/password values remain in OpenBao; only a `SecretReference` and field names are stored in PostgreSQL;
- the browser never receives credential values, and Temporal/Worker payloads carry connector/task/workflow identifiers rather than the Rotki credentials;
- `ROTKI_URL` is deployment-owned and cannot be replaced by connector metadata or a secret value;
- synchronization is a durable A1 `finance.sync.rotki` capability that reads provider state and writes only sourced Finance observations;
- adapter errors retain the last successful Finance snapshot rather than erasing it;
- repeated observations update stable source/account/position identities;
- extended public keys are not persisted by the first adapter slice even though they are not signing secrets, because they are high-value privacy data;
- Rotki provides no signing, send or broadcast authority to KAIRO.

ADR-015 and ADR-036 define the signing/provenance boundary. ADR-037 defines the concrete Rotki connector boundary.

## Tools and external capabilities

The Tools workspace is a policy/control surface over KAIRO's canonical MCP registry. It must not treat discovery as authorization.

A newly registered ToolServer starts disabled. Enabling a server does not automatically enable its tools; each tool remains explicitly policy-controlled. Remote contract drift and execution-time contract checks remain Core/Worker authority boundaries, not UI assumptions.

## Performance contract

The renderer must be built for graceful degradation from its first implementation.

Required mechanisms:

- instanced node geometry
- batched/efficient filament rendering
- layout/physics outside the React render loop
- adaptive DPR and effect quality
- level-of-detail
- frustum/camera culling where useful
- bounded label count
- reduced-motion and energy-saving modes

Target: 60 FPS on a reasonably modern machine when possible, with automatic degradation before interaction becomes sluggish.

The 2D map must also remain bounded by the server projection rather than attempting to visualize an entire unbounded account graph.

## Accessibility

No information may be communicated only through color or motion.

The same graph projection must be exposable as a linear/tree-like neighborhood inspector for keyboard and assistive technology. `prefers-reduced-motion` must disable nonessential movement and greatly reduce ambient animation.

Specialist workspaces must remain keyboard-operable and must not require the 3D view to create, locate or inspect canonical objects.

## Migration from the technical prototype

The product entrypoint is the permanent KAIRO Cockpit. The earlier capability-demo `App.tsx`/dashboard layout must not survive as a second frontend.

Working Command, News and Research capability access is preserved through the stable assistant/command surfaces while specialist features occupy the same shell.

## Acceptance boundary

Test Interface v1 is structurally complete when:

1. real canonical KAIRO data populates Home through the graph read model;
2. Home uses the production spatial engine, not a temporary graph component;
3. selection/focus/semantic zoom/history are functional;
4. the context rail is driven by real selected/attention/Today data;
5. Command can still invoke existing working capabilities;
6. no fake nodes or decorative semantic relationships are used;
7. the same graph package powers 3D, 2D and accessible KAIRO Brain views;
8. performance/reduced-motion modes are implemented in the same renderer family;
9. desktop/Tauri can reuse the same web application rather than requiring a second UI;
10. later feature work can extend Desktop/Voice and other areas without replacing the shell;
11. specialist workspaces that create or inspect canonical objects remain synchronized with the same graph projection and can navigate back to exact canonical entities;
12. external Calendar, Finance and future external-source overlays preserve explicit provenance rather than silently rewriting KAIRO-owned state;
13. Automations remain KAIRO-owned policy/audit state even when execution is delegated to Activepieces;
14. Finance/Crypto never exposes private signing material or a direct agent-signing path through the Cockpit;
15. concrete Finance connectors preserve credential custody outside browser/Temporal state and cannot expand read-only portfolio synchronization into signing authority.
