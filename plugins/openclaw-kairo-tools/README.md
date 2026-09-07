# KAIRO OpenClaw Tools

This package is the first runtime adapter between OpenClaw and KAIRO Core.

It deliberately exposes a very small tool surface:

- `kairo_project_create`
- `kairo_project_list`
- `kairo_project_get`
- `kairo_idea_capture`
- `kairo_idea_list`
- `kairo_idea_get`

The adapter does **not** let the model write KAIRO Markdown files directly. All durable writes go through `@kairo/core`, which owns validation, IDs, project isolation, provenance fields, and storage rules.

## Why this boundary matters

```text
model
  -> OpenClaw
    -> KAIRO tool
      -> KAIRO Core
        -> durable Markdown store
```

OpenClaw may be replaced in the future without changing the KAIRO domain data contract.

## Runtime configuration

The plugin requires one setting: an **absolute** runtime-private data path.

Example OpenClaw configuration fragment:

```json5
{
  plugins: {
    entries: {
      "kairo-tools": {
        enabled: true,
        config: {
          dataDir: "/var/lib/kairo/data"
        }
      }
    }
  }
}
```

Do not point `dataDir` inside the Git repository for a real deployment.

## Development

Requirements follow OpenClaw's current tool-plugin contract:

- supported Node 22+ runtime;
- OpenClaw pinned for development/validation;
- TypeScript ESM output;
- generated `openclaw.plugin.json` manifest.

From this directory:

```bash
npm install
npm run plugin:build
npm test
npm run plugin:validate
```

The build step uses OpenClaw's supported `defineToolPlugin` API and manifest generator.

## First vertical slice

Once installed into an OpenClaw development runtime, the first manual acceptance flow is:

1. Ask KAIRO to create a project named `ZTIKIX`.
2. Ask KAIRO to record a tentative idea in ZTIKIX.
3. Confirm the idea is stored as an `idea`, not a `decision` or `fact`.
4. Start a new OpenClaw session.
5. Ask KAIRO to list/retrieve the idea.
6. Confirm the original idea and provenance remain available from the same server-side KAIRO store.

This is the first half of V0 acceptance test AT-01. Background jobs come next; the Cockpit UI does not.
