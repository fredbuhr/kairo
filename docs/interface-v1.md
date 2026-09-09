# KAIRO Test Interface v1

Status: implementation contract for the first daily-use KAIRO interface.

This document freezes the architecture of the interface that will replace the current technical prototype. The goal is not to build a disposable UI and redesign it later. The first test interface is the product interface: later work may tune rendering, spacing, motion and information density, but should extend these boundaries rather than replace them.

## Product premise

KAIRO is not a dashboard, chatbot wrapper or decorative mind map.

The primary spatial surface is a navigable representation of KAIRO's canonical world model: projects, tasks, documents, conversations, people, agents, approvals, artefacts and other durable entities are nodes; known relationships are filaments.

The mycelium is functional UI. Decorative motion may exist, but a visible relationship must correspond to a real KAIRO relationship or an explicitly identified derived projection.

## Stable shell

The desktop layout has three coordinated surfaces:

1. **Primary navigation** — a restrained left rail for durable product areas.
2. **Spatial workspace** — the central KAIRO mycelium. It is the workspace, not a card inside the workspace.
3. **Context rail** — a right-side contextual surface that appears only when useful.

A compact KAIRO command dock is always available but never dominates the product. Long conversations may expand into a panel without turning Home into a chat application.

### Primary navigation

Initial product areas:

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

Projects and Tasks are the first non-spatial product areas activated in Test Interface v1. They remain part of the same shell and are backed directly by canonical KAIRO records.

### Specialist workspaces

Specialist workspaces do not create a second application shell. Projects, Tasks, Knowledge, Calendar, Gantt, Agents, Finance and later tools occupy the same central surface while preserving the primary navigation, universal search, command dock, assistant access and KAIRO identity.

A specialist workspace must use canonical KAIRO APIs or explicitly identified derived read models. It must not introduce its own authoritative project/task/document state merely because a tabular or form-oriented view is more convenient than the mycelium.

When a specialist view exposes an entity already represented spatially, it should provide a direct path back to that same canonical entity in KAIRO Brain. Creation or mutation in a specialist workspace must invalidate/update the shared graph projection so the world model and operational view converge without manual synchronization.

The first operational slices are Projects and Tasks. Their initial scope is intentionally simple: real create/read/filter/navigation behavior is preferable to a visually complete but fake workspace. Rich lifecycle actions may be added later without replacing the workspace boundary.

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

## One spatial engine

Home and KAIRO Brain use the same renderer and graph model.

Home applies a highly filtered, context-sensitive projection. KAIRO Brain exposes deeper navigation, filtering and inspection. There must not be a separate decorative Home graph and a second "real" graph later.

The engine is renderer-independent at the data/layout boundary:

- KAIRO Core decides which canonical entities and relationships are relevant;
- `@kairo/graph` defines the client graph contract and spatial state;
- the layout worker computes stable positions and clusters;
- React Three Fiber / Three.js renders the result;
- 2D and accessible projections consume the same graph contract.

## Canonical graph projection

PostgreSQL remains authoritative. Graphiti/Neo4j and Mem0 are derived projections and cannot silently become the source of product relationships.

The spatial UI consumes KAIRO-owned read models:

- `GET /v1/graph/home`
- `GET /v1/graph/neighborhood/{entity_type}/{entity_id}`
- `GET /v1/graph/search`

The read model may derive display-oriented properties such as importance, recency, relationship degree, cluster hints and level-of-detail. These values are presentation projections, not new canonical facts.

The read model may also expose canonical foreign-key relationships such as Task → Project. These are valid graph filaments even if they do not have a separate `relationships` row, because the underlying relationship is canonical.

## KAIRO system anchor

The KAIRO symbol may appear as a spatial anchor in the global view.

It is a UI/system anchor, not a fake domain entity. User data must never be fabricated merely to make the scene visually richer. Empty accounts therefore show the KAIRO anchor and onboarding actions rather than synthetic projects or connections.

## Spatial behavior

The final test renderer must support:

- hover
- selection
- contextual focus
- semantic zoom
- limited orbit/rotation
- pan
- branch isolation
- search → focus
- navigation history and recenter
- type/relation filtering
- deterministic/stable spatial seeding
- dynamic clustering
- organic node appearance
- activity pulses from real KAIRO events
- reduced-motion mode
- adaptive quality modes
- accessible non-3D projection

### Semantic zoom

Camera distance alone is not enough. The visible information changes with conceptual depth.

- global: dominant projects/contexts and urgent attention
- intermediate: real projects, tasks, documents, conversations and active actors
- close: secondary objects and explicit relationships
- detail: relationship explanations, provenance and satellites

The server limits the projection; the renderer applies visual LOD. A large account must not send or render every entity at once.

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

## Interaction contract

### Hover

The hovered node becomes slightly clearer. Direct relationships gain salience and unrelated content recedes. A compact label may show entity type, role/context and recent activity.

### Click

Selects the node, stabilizes its immediate neighborhood and drives the context rail.

### Double click / Explore

Focuses the selected entity and requests its neighborhood projection. Double click is a desktop shortcut; an explicit Explore action must exist for touch and accessibility.

### Natural-language navigation

Assistant requests may return typed UI focus/highlight directives. A model never receives direct Three.js authority. The frontend validates and applies KAIRO-owned UI directives.

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

## Accessibility

No information may be communicated only through color or motion.

The same graph projection must be exposable as a linear/tree-like neighborhood inspector for keyboard and assistive technology. `prefers-reduced-motion` must disable nonessential movement and greatly reduce ambient animation.

Specialist workspaces must remain keyboard-operable and must not require the 3D view to create, locate or inspect canonical objects.

## Migration from the current prototype

The current `App.tsx` is a capability demonstration surface, not a product shell.

The replacement must preserve working Command, News and Research capability access while extracting them into stable features. News/Research must not be deleted merely because their current large forms disappear from Home.

Once Test Interface v1 is accepted, the old dashboard/grid-of-planned-workspaces layout is removed rather than maintained as a second frontend.

## Acceptance boundary

Test Interface v1 is considered structurally complete when:

1. real canonical KAIRO data populates Home through the graph read model;
2. Home uses the production spatial engine, not a temporary graph component;
3. selection/focus/semantic zoom/history are functional;
4. the context rail is driven by real selected/attention data;
5. Command can still invoke existing working capabilities;
6. no fake nodes or decorative data relationships are used;
7. the same graph package can power the deeper KAIRO Brain view;
8. performance/reduced-motion modes are implemented in the same renderer;
9. desktop/Tauri can reuse the same web application rather than requiring a second UI;
10. later feature work can fill Projects, Knowledge, Calendar, Gantt, Finance and other areas without replacing the shell;
11. specialist workspaces that create or inspect canonical objects remain synchronized with the same graph projection and can navigate back to those exact entities.
