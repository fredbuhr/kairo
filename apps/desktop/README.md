# KAIRO Desktop

KAIRO Desktop is the Tauri trust boundary around the **same KAIRO Web Cockpit** used in the browser. It is not a second frontend and must not fork product state or navigation.

## Current slice

The desktop shell is initialized in Block 3 so daily-use testing can exercise the permanent interface before voice/device features are added.

Implemented now:

- Tauri v2 shell loading `apps/web` in development and bundling the same web build for desktop;
- a small KAIRO-owned IPC bridge that reports local capabilities;
- explicit clipboard read/write commands;
- explicit local notification command;
- browser/WebView file input remains the only file-import path, so broad filesystem permissions are **not** granted;
- Settings displays the actual runtime and never claims screenshot, microphone or global-shortcut support before those bridges exist.

Not enabled yet:

- screenshot/capture bridge;
- microphone / VAD / wake word / transcription;
- global summon shortcut;
- arbitrary filesystem access;
- privileged local command execution.

Those capabilities must be added one at a time with explicit permissions and policy/audit contracts rather than by exposing a generic shell to the frontend or to an agent.

## Run

From the repository root:

```bash
pnpm install
pnpm dev:desktop
```

The Tauri development shell starts the existing `@kairo/web` Vite application automatically.

To compile the desktop binary without producing platform installers:

```bash
pnpm build:desktop
```

## Trust model

The browser-compatible React application owns UI interaction state only. Native capabilities are invoked through typed, bounded Tauri commands. The frontend does not receive a generic Rust command channel, shell execution authority, unrestricted filesystem scopes or signing material.

The desktop shell is therefore an extension of the permanent Cockpit, not a place to bypass KAIRO Core policy. Future device actions that can affect external state must still cross the appropriate KAIRO policy/approval boundary.
