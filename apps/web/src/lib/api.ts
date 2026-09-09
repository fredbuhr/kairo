import type {
  KairoGraphEntityRef,
  KairoGraphProjection,
  KairoGraphSearchResult,
  KairoGraphUIDirectiveResolution,
} from '@kairo/graph'

export const API_URL = (import.meta.env.VITE_KAIRO_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export type ProjectRecord = {
  id: string
  name: string
  status: string
  summary?: string | null
  parent_id?: string | null
  created_at: string
  updated_at: string
}

export type TaskRecord = {
  id: string
  project_id: string
  title: string
  description?: string | null
  status: string
  owner_type: string
  owner_ref?: string | null
  authority_ceiling: number
  budget_usd?: string | number | null
  input: Record<string, unknown>
  started_at?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

export type ProjectCreateInput = {
  name: string
  status?: string
  summary?: string | null
  parent_id?: string | null
}

export type TaskCreateInput = {
  project_id: string
  title: string
  description?: string | null
  owner_type?: string
  owner_ref?: string | null
  authority_ceiling?: number
  budget_usd?: number | null
  input?: Record<string, unknown>
}

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

export function fetchProjects(): Promise<ProjectRecord[]> {
  return apiJson('/v1/projects')
}

export function createProject(input: ProjectCreateInput): Promise<ProjectRecord> {
  return apiJson('/v1/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: input.name,
      status: input.status || 'active',
      summary: input.summary || null,
      parent_id: input.parent_id || null,
    }),
  })
}

export function fetchTasks(): Promise<TaskRecord[]> {
  return apiJson('/v1/tasks')
}

export function createTask(input: TaskCreateInput): Promise<TaskRecord> {
  return apiJson('/v1/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: input.project_id,
      title: input.title,
      description: input.description || null,
      owner_type: input.owner_type || 'user',
      owner_ref: input.owner_ref || null,
      authority_ceiling: input.authority_ceiling ?? 1,
      budget_usd: input.budget_usd ?? null,
      input: input.input || {},
    }),
  })
}
