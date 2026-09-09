import { apiJson, type ProjectRecord } from './api'

export type ProjectUpdateInput = {
  name?: string
  status?: string
  summary?: string | null
  parent_id?: string | null
}

export function updateProject(projectId: string, input: ProjectUpdateInput): Promise<ProjectRecord> {
  return apiJson(`/v1/projects/${encodeURIComponent(projectId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}
