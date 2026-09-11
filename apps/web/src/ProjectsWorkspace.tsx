import { FormEvent, useEffect, useMemo, useState } from 'react'

import { usePagedCollection } from './lib/usePagedCollection'
import { kairoFetch } from './lib/apiClient'
import { useProjectSelection } from './lib/projectSelection'

type Project = {
  id: string
  name: string
  status: string
  summary?: string | null
  parent_id?: string | null
  created_at: string
  updated_at: string
}

type Task = {
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

type Props = {
  apiUrl: string
}

const TASK_STATUS_ORDER = ['todo', 'queued', 'running', 'completed', 'failed'] as const

async function readJson<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    const message = typeof detail === 'string' ? detail : detail?.message
    throw new Error(message || `KAIRO Core répond ${response.status}`)
  }
  return body as T
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    active: 'actif',
    todo: 'à faire',
    queued: 'en file',
    running: 'en cours',
    completed: 'terminé',
    failed: 'échec',
  }
  return labels[status] || status
}

function formatDate(value?: string | null) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export default function ProjectsWorkspace({ apiUrl }: Props) {
  const { selectedProjectId, setSelectedProjectId } = useProjectSelection()
  const [newProjectName, setNewProjectName] = useState('')
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [creatingProject, setCreatingProject] = useState(false)
  const [creatingTask, setCreatingTask] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const projectPage = usePagedCollection<Project>(`${apiUrl}/v1/projects`, selectedProjectId ? `${apiUrl}/v1/projects/${selectedProjectId}` : null)
  const { items: projects, setItems: setProjects, loading } = projectPage
  const taskPage = usePagedCollection<Task>(selectedProjectId ? `${apiUrl}/v1/tasks?project_id=${encodeURIComponent(selectedProjectId)}` : null)
  const { items: tasks, setItems: setTasks } = taskPage

  useEffect(() => {
    if (!loading && !projectPage.error && !projects.some((project) => project.id === selectedProjectId) && (selectedProjectId || projects.length)) {
      setSelectedProjectId(projects.find((project) => project.status === 'active')?.id || projects[0]?.id || '')
    }
  }, [loading, projectPage.error, projects, selectedProjectId, setSelectedProjectId])

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) || null,
    [projects, selectedProjectId],
  )

  const selectedTasks = useMemo(
    () => tasks.filter((task) => task.project_id === selectedProjectId),
    [tasks, selectedProjectId],
  )

  const taskCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const task of selectedTasks) counts.set(task.status, (counts.get(task.status) || 0) + 1)
    return counts
  }, [selectedTasks])

  const taskStatusSummary = useMemo(
    () =>
      TASK_STATUS_ORDER.map((status) => [status, taskCounts.get(status) || 0] as const).filter(
        ([, count]) => count > 0,
      ),
    [taskCounts],
  )

  async function createProject(event: FormEvent) {
    event.preventDefault()
    const name = newProjectName.trim()
    if (!name) return

    setCreatingProject(true)
    setError(null)
    try {
      const response = await kairoFetch(`${apiUrl}/v1/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, status: 'active' }),
      })
      const project = await readJson<Project>(response)
      setProjects((current) => [project, ...current.filter((item) => item.id !== project.id)])
      setSelectedProjectId(project.id)
      setNewProjectName('')
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Impossible de créer le projet.')
    } finally {
      setCreatingProject(false)
    }
  }

  async function createTask(event: FormEvent) {
    event.preventDefault()
    const title = newTaskTitle.trim()
    if (!selectedProjectId || !title) return

    setCreatingTask(true)
    setError(null)
    try {
      const response = await kairoFetch(`${apiUrl}/v1/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: selectedProjectId,
          title,
          owner_type: 'user',
          authority_ceiling: 1,
          input: {},
        }),
      })
      const task = await readJson<Task>(response)
      setTasks((current) => [task, ...current.filter((item) => item.id !== task.id)])
      setNewTaskTitle('')
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Impossible de créer la tâche.')
    } finally {
      setCreatingTask(false)
    }
  }

  return (
    <section className="news-workspace" aria-labelledby="projects-heading">
      <div className="news-heading">
        <div>
          <span className="eyebrow">PROJECTS</span>
          <h2 id="projects-heading">Projets et tâches canoniques KAIRO.</h2>
        </div>
        <span className="run-state">{projects.length} projet(s) affiché(s)</span>
      </div>

      <form className="news-form" onSubmit={createProject}>
        <label className="query-field">
          <span>Nouveau projet</span>
          <input
            value={newProjectName}
            onChange={(event) => setNewProjectName(event.target.value)}
            maxLength={240}
            placeholder="Ex. Lancement KAIRO"
          />
        </label>
        <div className="news-controls">
          <button type="submit" disabled={creatingProject || !newProjectName.trim()}>
            {creatingProject ? 'Création…' : 'Créer le projet'}
          </button>
        </div>
      </form>

      {(error || projectPage.error || taskPage.error) && <div className="error-panel">{error || projectPage.error || taskPage.error}</div>}
      {projectPage.hasMore && <button type="button" disabled={loading} onClick={() => void projectPage.loadMore()}>Charger les projets suivants</button>}
      {loading && !error && (
        <div className="progress-panel">
          <strong>Chargement de vos projets KAIRO.</strong>
          <span>La liste est filtrée côté Core selon le propriétaire authentifié.</span>
        </div>
      )}

      {!loading && projects.length === 0 && !error && (
        <div className="progress-panel">
          <strong>Aucun projet personnel.</strong>
          <span>Créez le premier projet pour commencer à organiser les tâches KAIRO.</span>
        </div>
      )}

      {projects.length > 0 && (
        <>
          <div className="news-controls">
            <label>
              <span>Projet sélectionné</span>
              <select
                value={selectedProjectId}
                onChange={(event) => setSelectedProjectId(event.target.value)}
              >
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name} · {statusLabel(project.status)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {selectedProject && (
            <article className="briefing" aria-label="Détail du projet sélectionné">
              <div className="briefing-topline">
                <div>
                  <span className="eyebrow">PROJET SÉLECTIONNÉ</span>
                  <h3>{selectedProject.name}</h3>
                </div>
                <span className={`run-state run-state-${selectedProject.status}`}>
                  {statusLabel(selectedProject.status)}
                </span>
              </div>

              {selectedProject.summary && <div className="brief-summary">{selectedProject.summary}</div>}

              <div className="sources-title">
                <span>
                  {formatDate(selectedProject.created_at)
                    ? `Créé le ${formatDate(selectedProject.created_at)}`
                    : 'Date de création indisponible'}
                  {formatDate(selectedProject.updated_at)
                    ? ` · mis à jour le ${formatDate(selectedProject.updated_at)}`
                    : ''}
                </span>
                <span>
                  {selectedTasks.length} tâche(s) affichée(s)
                  {taskStatusSummary.length
                    ? ` · ${taskStatusSummary
                        .map(([status, count]) => `${statusLabel(status)} ${count}`)
                        .join(' · ')}`
                    : ''}
                </span>
              </div>
            </article>
          )}

          <form className="news-form" onSubmit={createTask}>
            <label className="query-field">
              <span>Nouvelle tâche</span>
              <input
                value={newTaskTitle}
                onChange={(event) => setNewTaskTitle(event.target.value)}
                maxLength={320}
                placeholder="Ex. Finaliser la première version du Cockpit"
              />
            </label>
            <div className="news-controls">
              <button
                type="submit"
                disabled={creatingTask || !selectedProjectId || !newTaskTitle.trim()}
              >
                {creatingTask ? 'Création…' : 'Ajouter la tâche'}
              </button>
            </div>
          </form>

          {taskPage.hasMore && <button type="button" disabled={taskPage.loading} onClick={() => void taskPage.loadMore()}>Charger les tâches suivantes</button>}
          <section className="sources" aria-label="Tâches du projet sélectionné">
            <div className="sources-title">
              <strong>Tâches du projet</strong>
              <span>{selectedTasks.length} élément(s)</span>
            </div>
            <div className="source-list">
              {selectedTasks.length === 0 && !taskPage.loading && !taskPage.error && (
                <div className="source-card">
                  <span className="source-id">0</span>
                  <div>
                    <strong>Aucune tâche pour le moment.</strong>
                    <small>Ajoutez une première action concrète à ce projet.</small>
                  </div>
                </div>
              )}
              {selectedTasks.map((task) => (
                <div className="source-card" key={task.id}>
                  <span className="source-id">{statusLabel(task.status)}</span>
                  <div>
                    <strong>{task.title}</strong>
                    {task.description && <small>{task.description}</small>}
                    <small>
                      {formatDate(task.created_at) ? `Créée le ${formatDate(task.created_at)}` : 'Création inconnue'}
                      {task.started_at && formatDate(task.started_at)
                        ? ` · démarrée le ${formatDate(task.started_at)}`
                        : ''}
                      {task.completed_at && formatDate(task.completed_at)
                        ? ` · terminée le ${formatDate(task.completed_at)}`
                        : ''}
                    </small>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </section>
  )
}
