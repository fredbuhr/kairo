import { FormEvent, useEffect, useMemo, useState } from 'react'

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

export default function ProjectsWorkspace({ apiUrl }: Props) {
  const [projects, setProjects] = useState<Project[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [newProjectName, setNewProjectName] = useState('')
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [loading, setLoading] = useState(true)
  const [creatingProject, setCreatingProject] = useState(false)
  const [creatingTask, setCreatingTask] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const [projectsResponse, tasksResponse] = await Promise.all([
          fetch(`${apiUrl}/v1/projects`),
          fetch(`${apiUrl}/v1/tasks`),
        ])
        const [loadedProjects, loadedTasks] = await Promise.all([
          readJson<Project[]>(projectsResponse),
          readJson<Task[]>(tasksResponse),
        ])
        if (cancelled) return

        setProjects(loadedProjects)
        setTasks(loadedTasks)
        setSelectedProjectId((current) => {
          if (current && loadedProjects.some((project) => project.id === current)) return current
          return loadedProjects.find((project) => project.status === 'active')?.id || loadedProjects[0]?.id || ''
        })
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Impossible de charger Projects.')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [apiUrl])

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

  async function createProject(event: FormEvent) {
    event.preventDefault()
    const name = newProjectName.trim()
    if (!name) return

    setCreatingProject(true)
    setError(null)
    try {
      const response = await fetch(`${apiUrl}/v1/projects`, {
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
      const response = await fetch(`${apiUrl}/v1/tasks`, {
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
        <span className="run-state">{projects.length} projet(s)</span>
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

      {error && <div className="error-panel">{error}</div>}
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
            <div className="route-chip">
              <span>{selectedProject.name}</span>
              <small>
                {statusLabel(selectedProject.status)} · {selectedTasks.length} tâche(s)
                {taskCounts.size
                  ? ` · ${Array.from(taskCounts.entries())
                      .map(([status, count]) => `${statusLabel(status)} ${count}`)
                      .join(' · ')}`
                  : ''}
              </small>
            </div>
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

          <section className="sources" aria-label="Tâches du projet sélectionné">
            <div className="sources-title">
              <strong>Tâches</strong>
              <span>{selectedTasks.length} élément(s) dans ce projet</span>
            </div>
            <div className="source-list">
              {selectedTasks.length === 0 && (
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
                    <small>
                      {task.owner_type}
                      {task.owner_ref ? ` · ${task.owner_ref}` : ''}
                      {task.started_at ? ' · démarrée' : ''}
                      {task.completed_at ? ' · terminée' : ''}
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
