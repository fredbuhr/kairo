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
  priority?: number
  planned_start_at?: string | null
  planned_end_at?: string | null
  due_at?: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

export type TodayRecord = {
  generated_at: string
  day_start: string
  day_end: string
  timezone_offset_minutes: number
  overdue: TaskRecord[]
  due_today: TaskRecord[]
  planned_today: TaskRecord[]
  important: TaskRecord[]
}

export type TaskPlanningUpdateInput = {
  title?: string
  description?: string | null
  status?: string
  priority?: number
  planned_start_at?: string | null
  planned_end_at?: string | null
  due_at?: string | null
}

export type AssetRecord = {
  id: string
  project_id?: string | null
  bucket: string
  object_key: string
  mime_type?: string | null
  size_bytes: number | null
  sha256?: string | null
  metadata_json: Record<string, unknown>
  created_at: string
}

export type DocumentRecord = {
  id: string
  asset_id: string
  project_id: string
  title: string
  media_type?: string | null
  source_sha256?: string | null
  status: string
  metadata_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type DocumentVersionRecord = {
  id: string
  document_id: string
  generation: number
  task_id?: string | null
  parser: string
  parser_version?: string | null
  source_sha256?: string | null
  status: string
  chunk_count: number
  metadata_json: Record<string, unknown>
  last_error?: string | null
  created_at: string
  completed_at?: string | null
}

export type DocumentChunkRecord = {
  id: string
  document_version_id: string
  ordinal: number
  text: string
  content_sha256: string
  metadata_json: Record<string, unknown>
  created_at: string
}

export type DocumentRunRecord = {
  document: DocumentRecord
  version: DocumentVersionRecord
  workflow_execution_id: string
  workflow_id: string
  workflow_status: string
}

export type KnowledgeSearchHit = {
  document_id: string
  document_title: string
  project_id: string
  media_type?: string | null
  version_id: string
  generation: number
  chunk_id: string
  ordinal: number
  excerpt: string
  metadata: Record<string, unknown>
}

export type KnowledgeSearchResult = {
  query: string
  results: KnowledgeSearchHit[]
}

export type AgentExecutionRecord = {
  task_id: string
  project_id: string
  title: string
  task_status: string
  capability: string
  authority_ceiling: number
  budget_usd?: string | number | null
  spent_usd: string | number
  pending_approvals: number
  workflow_execution_id?: string | null
  workflow_id?: string | null
  workflow_status?: string | null
  workflow_started_at?: string | null
  workflow_completed_at?: string | null
  last_error?: string | null
  command_id?: string | null
  created_at: string
  updated_at: string
  metadata: Record<string, unknown>
}

export type ApprovalRecord = {
  id: string
  task_id: string
  workflow_execution_id?: string | null
  requested_by: string
  action: string
  resource_type: string
  resource_id?: string | null
  authority_level: number
  reason: string
  scope_json: Record<string, unknown>
  status: string
  decided_by?: string | null
  decision_note?: string | null
  expires_at?: string | null
  decided_at?: string | null
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

export function fetchPlanningTasks(includeClosed = false): Promise<TaskRecord[]> {
  return apiJson(`/v1/planning/tasks?include_closed=${includeClosed ? 'true' : 'false'}`)
}

export function fetchToday(): Promise<TodayRecord> {
  const offset = -new Date().getTimezoneOffset()
  return apiJson(`/v1/today?timezone_offset_minutes=${offset}`)
}

export function updateTaskPlanning(taskId: string, input: TaskPlanningUpdateInput): Promise<TaskRecord> {
  return apiJson(`/v1/tasks/${encodeURIComponent(taskId)}/planning`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
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

export function fetchAgentExecutions(limit = 100): Promise<AgentExecutionRecord[]> {
  return apiJson(`/v1/operations/agents?limit=${limit}`)
}

export function fetchApprovalRequests(approvalStatus?: string): Promise<ApprovalRecord[]> {
  const query = approvalStatus ? `?approval_status=${encodeURIComponent(approvalStatus)}` : ''
  return apiJson(`/v1/approval-requests${query}`)
}

export function decideApproval(approvalId: string, decision: 'approved' | 'denied', note?: string): Promise<ApprovalRecord> {
  return apiJson(`/v1/approval-requests/${encodeURIComponent(approvalId)}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, note: note || null }),
  })
}

export function fetchDocuments(): Promise<DocumentRecord[]> {
  return apiJson('/v1/documents')
}

export function fetchDocumentVersions(documentId: string): Promise<DocumentVersionRecord[]> {
  return apiJson(`/v1/documents/${encodeURIComponent(documentId)}/versions`)
}

export function fetchDocumentChunks(versionId: string): Promise<DocumentChunkRecord[]> {
  return apiJson(`/v1/document-versions/${encodeURIComponent(versionId)}/chunks`)
}

export function searchKnowledge(query: string, limit = 24): Promise<KnowledgeSearchResult> {
  return apiJson(`/v1/knowledge/search?q=${encodeURIComponent(query)}&limit=${limit}`)
}

export function uploadAsset(file: File, projectId?: string | null): Promise<AssetRecord> {
  const body = new FormData()
  body.set('file', file)
  if (projectId) body.set('project_id', projectId)
  return apiJson('/v1/assets', { method: 'POST', body })
}

export function createDocument(assetId: string, title?: string | null): Promise<DocumentRunRecord> {
  return apiJson('/v1/documents', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ asset_id: assetId, title: title || null }),
  })
}

export function reingestDocument(documentId: string): Promise<DocumentRunRecord> {
  return apiJson(`/v1/documents/${encodeURIComponent(documentId)}/reingest`, {
    method: 'POST',
  })
}
