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

The first desktop slice exposes:

- runtime/capability introspection;
- clipboard text read/write;
- local notifications, requesting OS permission only when notification delivery is actually invoked;
- opt-in background attention notifications derived only from KAIRO's sanitized canonical activity stream;
- ordinary user-selected WebView file input;
- one fixed native summon shortcut, `CmdOrCtrl+Shift+Space`, whose Rust handler may only restore/show/focus the main KAIRO window.

The frontend receives **no global-shortcut registration API**. It cannot claim arbitrary operating-system shortcuts merely because the native plugin is present.

Screenshot capture, microphone, wake word/VAD, user-configurable global shortcuts and privileged local commands remain explicitly unavailable until their individual contracts exist.

## Background attention notification boundary

Native notifications are useful only if they reduce the need to keep KAIRO visible constantly. They must not become a general-purpose channel that any agent or arbitrary frontend code can spam.

The current Cockpit therefore applies these rules:

- background attention notifications are disabled by default;
- the user explicitly enables the preference in Desktop Settings;
- notification delivery is attempted only in Tauri Desktop;
- the Cockpit does not issue the notification when the KAIRO window is visible and focused;
- only a fixed allow-list of canonical activity classes is eligible, currently approvals plus selected completion/failure events;
- the browser reacts to the sanitized graph activity event, not arbitrary downstream provider text;
- realtime event ids are deduplicated locally so reconnect/replay does not generate duplicate OS notifications;
- notification permission refusal or OS delivery failure remains a progressive-enhancement failure and never breaks realtime state or graph invalidation.

This preference is local presentation state. It grants no new execution authority to the agent, Worker or Core.

## Why file import remains WebView-selected initially

KAIRO already has a canonical Asset → Document ingestion boundary. A native desktop wrapper does not justify granting broad filesystem access merely to reproduce the browser's explicit file picker.

The first desktop version therefore continues to use the browser/WebView file-input path. A future selected-directory or watched-folder capability may be added, but it must receive a bounded scope and cannot silently become unrestricted disk access.

## Why the summon shortcut is registered in Rust

The shortcut is a shell capability, not product/domain state. Registering a single fixed shortcut in Rust lets KAIRO provide the expected “summon” behavior without exposing a generic shortcut-management surface to React or to model-driven code.

Its action is intentionally local and reversible: unminimize, show and focus the main window. It does not execute a Command, invoke an agent or cross an external side-effect boundary by itself.

## Consequences

### Positive

- Browser and desktop remain one product surface.
- The mycelium, Brain, Command Dock and specialist workspaces are not reimplemented.
- Native permissions stay visible and reviewable.
- Browser users receive truthful unsupported states instead of broken calls.
- The initial summon behavior exists without granting shortcut-registration authority to the frontend.
- Important background approvals/completions can reach the user without making every realtime event an OS notification.
- Future Tauri capabilities can be tested without granting agents generic operating-system authority.

### Trade-offs

- Some desktop features arrive later than they would with an unrestricted local sidecar.
- A production remote-server configuration and authenticated desktop session still need explicit hardening.
- Clipboard, notification and global-shortcut plugins add native build dependencies that must be validated on supported operating systems.
- The first shortcut is fixed rather than user-configurable; configurability requires a dedicated settings/permission contract.
- The first attention-notification allow-list is intentionally conservative and may need product tuning.

## Rejected alternatives

### Separate React desktop application

Rejected because it would immediately duplicate the permanent Cockpit and violate the one-interface decision.

### Generic Tauri shell/command bridge

Rejected because arbitrary command execution would collapse the security boundary between model/UI code and the host machine.

### Frontend-managed global shortcut plugin

Rejected for the first slice because it would give the WebView a broader OS-level registration capability than the product currently needs.

### Notify every realtime event

Rejected because it would turn the operating system notification center into another noisy activity feed and make model/connector chatter visible as user attention demands.

### Broad filesystem permission from day one

Rejected because explicit user-selected file import already works and broader access has no justified first-slice requirement.

## Follow-up

Future desktop work should proceed capability by capability:

1. authenticated/runtime server configuration;
2. user-configurable summon shortcut only after a bounded registration contract exists;
3. screenshot/capture with explicit user scope and provenance;
4. microphone/VAD/voice with visible recording state and permission handling;
5. selected filesystem scopes/watched folders;
6. approved local actions only through KAIRO policy and audit boundaries.
