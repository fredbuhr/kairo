import { apiJson } from './api'

export type ToolServerRecord = {
  id: string
  key: string
  namespace: string
  title: string
  endpoint_url: string
  transport: 'mcp_streamable_http' | string
  enabled: boolean
  catalog_generation: number
  metadata_json: Record<string, unknown>
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
  output_schema?: Record<string, unknown> | null
  remote_annotations: Record<string, unknown>
  schema_hash: string
  risk_class: 'read' | 'write' | 'destructive'
  retry_policy: 'safe_retry' | 'no_retry'
  authority_level: number
  estimated_cost_usd: string | number
  enabled: boolean
  available: boolean
  last_seen_at?: string | null
  created_at: string
  updated_at: string
}

export type ToolServerCreateInput = {
  key: string
  namespace: string
  title: string
  endpoint_url: string
  transport?: 'mcp_streamable_http'
  metadata?: Record<string, unknown>
}

export function fetchToolServers(): Promise<ToolServerRecord[]> {
  return apiJson('/v1/tool-servers')
}

export function createToolServer(input: ToolServerCreateInput): Promise<ToolServerRecord> {
  return apiJson('/v1/tool-servers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      key: input.key,
      namespace: input.namespace,
      title: input.title,
      endpoint_url: input.endpoint_url,
      transport: input.transport || 'mcp_streamable_http',
      metadata: input.metadata || {},
    }),
  })
}

export function fetchTools(): Promise<ToolDefinitionRecord[]> {
  return apiJson('/v1/tools')
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
    enabled?: boolean
    risk_class?: 'read' | 'write' | 'destructive'
    retry_policy?: 'safe_retry' | 'no_retry'
    authority_level?: number
    estimated_cost_usd?: number
  },
): Promise<ToolDefinitionRecord> {
  return apiJson(`/v1/tools/${encodeURIComponent(toolKey)}/policy`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}
