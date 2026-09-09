import { invoke } from '@tauri-apps/api/core'

export type KairoDesktopCapabilities = {
  runtime: 'web' | 'tauri'
  app_version?: string | null
  platform?: string | null
  arch?: string | null
  file_import: 'web_file_input' | 'unsupported'
  clipboard_read: boolean
  clipboard_write: boolean
  notifications: boolean
  screenshots: boolean
  microphone: boolean
  summon_shortcut: boolean
}

const WEB_CAPABILITIES: KairoDesktopCapabilities = {
  runtime: 'web',
  app_version: null,
  platform: null,
  arch: null,
  file_import: 'web_file_input',
  clipboard_read: false,
  clipboard_write: false,
  notifications: false,
  screenshots: false,
  microphone: false,
  summon_shortcut: false,
}

export function isKairoDesktopRuntime() {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
}

export async function fetchDesktopCapabilities(): Promise<KairoDesktopCapabilities> {
  if (!isKairoDesktopRuntime()) return WEB_CAPABILITIES
  return invoke<KairoDesktopCapabilities>('desktop_capabilities')
}

function requireDesktopRuntime() {
  if (!isKairoDesktopRuntime()) {
    throw new Error('Cette capacité locale est disponible uniquement dans KAIRO Desktop.')
  }
}

export async function readDesktopClipboard(): Promise<string> {
  requireDesktopRuntime()
  return invoke<string>('desktop_read_clipboard')
}

export async function writeDesktopClipboard(text: string): Promise<void> {
  requireDesktopRuntime()
  await invoke('desktop_write_clipboard', { text })
}

export async function sendDesktopNotification(title: string, body: string): Promise<void> {
  requireDesktopRuntime()
  await invoke('desktop_notify', { title, body })
}
