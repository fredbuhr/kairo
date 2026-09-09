# ADR-038 — KAIRO Desktop reuses the Cockpit and bounds native capabilities

Status: accepted

Date: 2026-09-09

## Context

KAIRO needs a desktop presence for capabilities that a normal browser cannot reliably or safely provide: clipboard integration, notifications, global summon shortcuts, screenshots, microphone/voice, selected filesystem access and later tightly controlled local actions.

The permanent Test Interface v1 already lives in `apps/web`. Building a separate desktop frontend would duplicate navigation, state handling, graph rendering and specialist workspaces, and would almost certainly cause the browser and desktop products to diverge.

At the same time, wrapping the web UI in a desktop runtime must not accidentally create a generic local-execution backdoor for the frontend or for model-driven agents.

## Decision

`apps/desktop` is a **Tauri v2 trust boundary around the same `apps/web` build**.

The desktop application:

1. uses the existing KAIRO Cockpit as its frontend in development and production builds;
2. exposes native functionality only through narrow KAIRO-owned IPC commands;
3. reports capability availability explicitly so the web UI can degrade truthfully in a normal browser;
4. grants no generic shell execution or arbitrary filesystem access to the frontend;
5. keeps external-state authority in KAIRO Core policy/approval flows rather than treating Tauri as a policy bypass;
6. adds sensitive native capabilities incrementally, with an explicit permission and provenance design for each capability.

The first desktop slice exposes only:

- runtime/capability introspection;
- clipboard text read/write;
- local notifications;
- ordinary user-selected WebView file input.

Screenshot capture, microphone, wake word/VAD, global summon shortcuts and privileged local commands remain explicitly unavailable until their individual contracts exist.

## Why file import remains WebView-selected initially

KAIRO already has a canonical Asset → Document ingestion boundary. A native desktop wrapper does not justify granting broad filesystem access merely to reproduce the browser's explicit file picker.

The first desktop version therefore continues to use the browser/WebView file-input path. A future selected-directory or watched-folder capability may be added, but it must receive a bounded scope and cannot silently become unrestricted disk access.

## Consequences

### Positive

- Browser and desktop remain one product surface.
- The mycelium, Brain, Command Dock and specialist workspaces are not reimplemented.
- Native permissions stay visible and reviewable.
- Browser users receive truthful unsupported states instead of broken calls.
- Future Tauri capabilities can be tested without granting agents generic operating-system authority.

### Trade-offs

- Some desktop features arrive later than they would with an unrestricted local sidecar.
- A production remote-server configuration and authenticated desktop session still need explicit hardening.
- Clipboard and notification plugins add native build dependencies that must be validated on supported operating systems.

## Rejected alternatives

### Separate React desktop application

Rejected because it would immediately duplicate the permanent Cockpit and violate the one-interface decision.

### Generic Tauri shell/command bridge

Rejected because arbitrary command execution would collapse the security boundary between model/UI code and the host machine.

### Broad filesystem permission from day one

Rejected because explicit user-selected file import already works and broader access has no justified first-slice requirement.

## Follow-up

Future desktop work should proceed capability by capability:

1. authenticated/runtime server configuration;
2. global summon shortcut and window-focus behavior;
3. screenshot/capture with explicit user scope and provenance;
4. microphone/VAD/voice with visible recording state and permission handling;
5. selected filesystem scopes/watched folders;
6. approved local actions only through KAIRO policy and audit boundaries.
