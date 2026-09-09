use serde::Serialize;
use tauri::{plugin::PermissionState, Manager};
use tauri_plugin_clipboard_manager::ClipboardExt;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};
use tauri_plugin_notification::NotificationExt;

const SUMMON_SHORTCUT: &str = "CmdOrCtrl+Shift+Space";

#[derive(Debug, Serialize)]
struct DesktopCapabilities {
    runtime: &'static str,
    app_version: String,
    platform: &'static str,
    arch: &'static str,
    file_import: &'static str,
    clipboard_read: bool,
    clipboard_write: bool,
    notifications: bool,
    screenshots: bool,
    microphone: bool,
    summon_shortcut: bool,
    summon_shortcut_label: &'static str,
}

#[tauri::command]
fn desktop_capabilities(app: tauri::AppHandle) -> DesktopCapabilities {
    DesktopCapabilities {
        runtime: "tauri",
        app_version: app.package_info().version.to_string(),
        platform: std::env::consts::OS,
        arch: std::env::consts::ARCH,
        // File import deliberately remains the same explicit user-selected browser/WebView flow as
        // KAIRO Web in this first slice. Broad arbitrary filesystem access is not granted here.
        file_import: "web_file_input",
        clipboard_read: true,
        clipboard_write: true,
        notifications: true,
        screenshots: false,
        microphone: false,
        summon_shortcut: true,
        summon_shortcut_label: SUMMON_SHORTCUT,
    }
}

#[tauri::command]
fn desktop_read_clipboard(app: tauri::AppHandle) -> Result<String, String> {
    app.clipboard().read_text().map_err(|error| error.to_string())
}

#[tauri::command]
fn desktop_write_clipboard(app: tauri::AppHandle, text: String) -> Result<(), String> {
    if text.len() > 1_000_000 {
        return Err("clipboard payload exceeds the KAIRO desktop limit".into());
    }
    app.clipboard()
        .write_text(text)
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn desktop_notify(app: tauri::AppHandle, title: String, body: String) -> Result<(), String> {
    let title = title.trim();
    let body = body.trim();
    if title.is_empty() || title.len() > 120 {
        return Err("notification title must contain 1-120 characters".into());
    }
    if body.len() > 1_000 {
        return Err("notification body exceeds 1000 characters".into());
    }

    let notifications = app.notification();
    let state = notifications
        .permission_state()
        .map_err(|error| error.to_string())?;
    let state = if state == PermissionState::Unknown {
        notifications
            .request_permission()
            .map_err(|error| error.to_string())?
    } else {
        state
    };
    if state != PermissionState::Granted {
        return Err("notification permission was not granted".into());
    }

    notifications
        .builder()
        .title(title)
        .body(body)
        .show()
        .map_err(|error| error.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state() != ShortcutState::Pressed {
                        return;
                    }
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.unminimize();
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                })
                .build(),
        )
        .setup(|app| {
            // One fixed summon shortcut is registered by Rust. The frontend receives no generic
            // register/unregister permission, so UI/model code cannot claim arbitrary OS hotkeys.
            app.global_shortcut().register(SUMMON_SHORTCUT)?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            desktop_capabilities,
            desktop_read_clipboard,
            desktop_write_clipboard,
            desktop_notify,
        ])
        .run(tauri::generate_context!())
        .expect("error while running KAIRO Desktop");
}
