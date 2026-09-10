import { kairoFetch } from './lib/apiClient'

export type CapabilityArtifact = {
  id: string
  kind: string
  title: string
  content: Record<string, unknown>
}

export type CapabilityTaskView = {
  taskId: string
  capability: string
  status: string
  executionStatus?: string | null
  title?: string | null
  answer?: string | null
  error?: string | null
  artifact?: CapabilityArtifact | null
  raw: unknown
}

type TaskRead = {
  id: string
  title: string
  status: string
}

type ArtifactRead = {
  id: string
  kind: string
  title: string
  content: Record<string, unknown>
}

type NewsBriefRead = {
  task_id: string
  status: string
  artifact?: ArtifactRead | null
}

type ResearchRunRead = {
  task_id: string
  status: string
  execution_status?: string | null
  answer?: string | null
  error?: string | null
  artifact_id?: string | null
}

async function readJson<T>(url: string): Promise<T> {
  const response = await kairoFetch(url)
  if (!response.ok) {
    throw new Error(`KAIRO Core répond ${response.status}`)
  }
  return (await response.json()) as T
}

function normalizeArtifact(value: ArtifactRead | null | undefined): CapabilityArtifact | null {
  if (!value) return null
  return {
    id: value.id,
    kind: value.kind,
    title: value.title,
    content: value.content || {},
  }
}

export async function loadCapabilityTask(
  apiUrl: string,
  capability: string,
  taskId: string,
): Promise<CapabilityTaskView> {
  if (capability === 'news.brief') {
    const brief = await readJson<NewsBriefRead>(`${apiUrl}/v1/news/briefs/${taskId}`)
    return {
      taskId,
      capability,
      status: brief.status,
      artifact: normalizeArtifact(brief.artifact),
      raw: brief,
    }
  }

  if (capability === 'research.autonomous') {
    const research = await readJson<ResearchRunRead>(`${apiUrl}/v1/research/runs/${taskId}`)
    const artifacts = research.artifact_id
      ? await readJson<ArtifactRead[]>(`${apiUrl}/v1/tasks/${taskId}/artifacts`)
      : []
    const artifact = artifacts.find((item) => item.id === research.artifact_id) || null
    return {
      taskId,
      capability,
      status: research.status,
      executionStatus: research.execution_status,
      answer: research.answer,
      error: research.error,
      artifact: normalizeArtifact(artifact),
      raw: research,
    }
  }

  const [task, artifacts] = await Promise.all([
    readJson<TaskRead>(`${apiUrl}/v1/tasks/${taskId}`),
    readJson<ArtifactRead[]>(`${apiUrl}/v1/tasks/${taskId}/artifacts`),
  ])
  const latestArtifact = artifacts.length ? artifacts[artifacts.length - 1] : null
  return {
    taskId,
    capability,
    status: task.status,
    title: task.title,
    artifact: normalizeArtifact(latestArtifact),
    raw: { task, artifacts },
  }
}

export function isTerminalTaskStatus(status: string): boolean {
  return status === 'completed' || status === 'failed'
}
