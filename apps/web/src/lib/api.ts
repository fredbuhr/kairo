import type {
  KairoGraphEntityRef,
  KairoGraphProjection,
  KairoGraphSearchResult,
  KairoGraphUIDirectiveResolution,
} from '@kairo/graph'

export const API_URL = (import.meta.env.VITE_KAIRO_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    const message =
      (typeof detail === 'string' && detail) ||
      detail?.message ||
      body?.message ||
      `KAIRO Core répond ${response.status}`
    throw new Error(message)
  }
  return body as T
}

export function fetchGraphHome(maxNodes = 72): Promise<KairoGraphProjection> {
  return apiJson(`/v1/graph/home?max_nodes=${maxNodes}`)
}

export function fetchGraphNeighborhood(
  entity: KairoGraphEntityRef,
  depth = 1,
  maxNodes = 96,
): Promise<KairoGraphProjection> {
  return apiJson(
    `/v1/graph/neighborhood/${encodeURIComponent(entity.entity_type)}/${encodeURIComponent(entity.entity_id)}?depth=${depth}&max_nodes=${maxNodes}`,
  )
}

export function searchGraph(query: string, limit = 18): Promise<KairoGraphSearchResult> {
  return apiJson(`/v1/graph/search?q=${encodeURIComponent(query)}&limit=${limit}`)
}

export function resolveGraphDirective(text: string): Promise<KairoGraphUIDirectiveResolution> {
  return apiJson('/v1/graph/directives/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
}
