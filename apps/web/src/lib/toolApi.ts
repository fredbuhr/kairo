import { apiJson } from './api'

export type ToolServerRecord = {
  id: string
  key: string
  title: string
  endpoint_url: string
  transport: string
  auth_mode: string
  enabled: boolean
  metadata: Record<string, unknown>
  catalog_generation: number
  last_sync_at?: string | null
  last_sync_error?: string | null
  created_at: string
  updated_at: string
}

export type ToolDefinitionRecord = {
  id: string
  server_id: string
  key: string
  remote_name: string
  title: string
  description?: string | null
  input_schema: Record<string, unknown>
  output_schema: Record<string, unknown>
  schema_hash: string
  risk_class: 'read' | 'write' | 'dangerous'
  retry_policy: 'safe_retry' | 'no_retry_after_start'
  authority_level: number
  estimated_cost_usd: string | number
  enabled: boolean
  available: boolean
  catalog_generation: number
  metadata: Record<string, unknown>
  last_seen_at?: string | null
  created_at: string
  updated_at: string
}

export function fetchToolServers(): Promise<ToolServerRecord[]> {
  return apiJson('/v1/tool-servers')
}

export function fetchTools(serverKey?: string): Promise<ToolDefinitionRecord[]> {
  const query = serverKey ? `?server_key=${encodeURIComponent(serverKey)}` : ''
  return apiJson(`/v1/tools${query}`)
}

export function syncToolServer(serverKey: string): Promise<{ server_key: string; catalog_generation: number; discovered: number; available: number; unavailable: number }> {
  return apiJson(`/v1/tool-servers/${encodeURIComponent(serverKey)}/sync`, { method: 'POST' })
}

export function updateToolServerPolicy(serverKey: string, enabled: boolean): Promise<ToolServerRecord> {
  return apiJson(`/v1/tool-servers/${encodeURIComponent(serverKey)}/policy`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  })
}

export function updateToolPolicy(
  toolKey: string,
  input: {
    enabled: boolean
    risk_class?: 'read' | 'write' | 'dangerous'
    retry_policy?: 'safe_retry' | 'no_retry_after_start'
    authority_level?: number
    estimated_cost_usd?: number
    metadata?: Record<string, unknown>
  },
): Promise<ToolDefinitionRecord> {
  return apiJson(`/v1/tools/${encodeURIComponent(toolKey)}/policy`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}
