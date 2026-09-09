import { FormEvent, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { KairoGraphEntityRef } from '@kairo/graph'

import {
  createProject,
  createTask,
  fetchProjects,
  fetchTasks,
  type ProjectRecord,
  type TaskRecord,
} from '../../lib/api'

export type CoreWorkspaceMode = 'projects' | 'tasks'

function shortDate(value: string) {
  try {
    return new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short' }).format(new Date(value))
  } catch {
    return value
  }
}

function taskStatusLabel(value: string) {
  const labels: Record<string, string> = {
    todo: 'À faire',
    pending: 'En attente',
    queued: 'Planifiée',
    running: 'En cours',
    in_progress: 'En cours',
    waiting: 'En attente',
    waiting_approval: 'Approbation requise',
    blocked: 'Bloquée',
    completed: 'Terminée',
    done: 'Terminée',
    failed: 'Échec',
    cancelled: 'Annulée',
  }
  return labels[value] || value
}

function ProjectForm({ projects }: { projects: ProjectRecord[] }) {
  const client = useQueryClient()
  const [name, setName] = useState('')
  const [summary, setSummary] = useState('')
  const [parentId, setParentId] = useState('')
  const mutation = useMutation({
    mutationFn: () => createProject({
      name: name.trim(),
      summary: summary.trim() || null,
      parent_id: parentId || null,
    }),
    onSuccess: async () => {
      setName('')
      setSummary('')
      setParentId('')
      await Promise.all([
        client.invalidateQueries({ queryKey: ['projects'] }),
        client.invalidateQueries({ queryKey: ['kairo-graph'] }),
      ])
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim() || mutation.isPending) return
    mutation.mutate()
  }

  return (
    <form className="workspace-create" onSubmit={submit}>
      <div className="workspace-create-heading">
        <div><span className="kairo-kicker">NOUVEAU</span><strong>Créer un projet</strong></div>
        <button type="submit" disabled={!name.trim() || mutation.isPending}>{mutation.isPending ? 'Création…' : 'Créer'}</button>
      </div>
      <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Nom du projet" maxLength={240} />
      <textarea value={summary} onChange={(event) => setSummary(event.target.value)} placeholder="Résumé optionnel" rows={3} />
      <select value={parentId} onChange={(event) => setParentId(event.target.value)}>
        <option value="">Aucun projet parent</option>
        {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
      </select>
      {mutation.isError && <small className="workspace-error">{mutation.error instanceof Error ? mutation.error.message : 'Création impossible.'}</small>}
    </form>
  )
}

function TaskForm({ projects }: { projects: ProjectRecord[] }) {
  const client = useQueryClient()
  const [projectId, setProjectId] = useState(projects[0]?.id || '')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const mutation = useMutation({
    mutationFn: () => createTask({
      project_id: projectId,
      title: title.trim(),
      description: description.trim() || null,
    }),
    onSuccess: async () => {
      setTitle('')
      setDescription('')
      await Promise.all([
        client.invalidateQueries({ queryKey: ['tasks'] }),
        client.invalidateQueries({ queryKey: ['kairo-graph'] }),
      ])
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!projectId || !title.trim() || mutation.isPending) return
    mutation.mutate()
  }

  return (
    <form className="workspace-create" onSubmit={submit}>
      <div className="workspace-create-heading">
        <div><span className="kairo-kicker">NOUVELLE</span><strong>Créer une tâche</strong></div>
        <button type="submit" disabled={!projectId || !title.trim() || mutation.isPending}>{mutation.isPending ? 'Création…' : 'Créer'}</button>
      </div>
      <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
        <option value="">Choisir un projet</option>
        {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
      </select>
      <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Titre de la tâche" maxLength={320} />
      <textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description optionnelle" rows={3} />
      {mutation.isError && <small className="workspace-error">{mutation.error instanceof Error ? mutation.error.message : 'Création impossible.'}</small>}
    </form>
  )
}

function ProjectsWorkspace({
  projects,
  tasks,
  onExploreEntity,
}: {
  projects: ProjectRecord[]
  tasks: TaskRecord[]
  onExploreEntity: (entity: KairoGraphEntityRef) => void
}) {
  const taskCounts = useMemo(() => {
    const counts = new Map<string, { open: number; total: number }>()
    for (const task of tasks) {
      const current = counts.get(task.project_id) || { open: 0, total: 0 }
      current.total += 1
      if (!['completed', 'done', 'cancelled'].includes(task.status)) current.open += 1
      counts.set(task.project_id, current)
    }
    return counts
  }, [tasks])

  return (
    <div className="workspace-layout">
      <section className="workspace-main">
        <header className="workspace-title">
          <div><span className="kairo-kicker">PROJETS</span><h1>Vos projets</h1><p>La même réalité canonique que dans le mycélium, présentée ici pour travailler plus directement.</p></div>
          <strong>{projects.length}</strong>
        </header>

        {projects.length === 0 ? (
          <div className="workspace-empty"><strong>Aucun projet pour l’instant.</strong><span>Créez votre premier projet : il apparaîtra aussi dans le cerveau KAIRO.</span></div>
        ) : (
          <div className="workspace-project-grid">
            {projects.map((project) => {
              const count = taskCounts.get(project.id) || { open: 0, total: 0 }
              return (
                <article className="workspace-project-card" key={project.id}>
                  <div className="workspace-project-topline"><span>{project.status}</span><small>{shortDate(project.updated_at)}</small></div>
                  <h2>{project.name}</h2>
                  <p>{project.summary || 'Aucun résumé.'}</p>
                  <div className="workspace-project-metrics"><span><strong>{count.open}</strong> ouvertes</span><span><strong>{count.total}</strong> tâches</span></div>
                  <button type="button" onClick={() => onExploreEntity({ entity_type: 'project', entity_id: project.id })}>Explorer dans KAIRO</button>
                </article>
              )
            })}
          </div>
        )}
      </section>
      <aside className="workspace-side"><ProjectForm projects={projects} /></aside>
    </div>
  )
}

function TasksWorkspace({
  projects,
  tasks,
  onExploreEntity,
}: {
  projects: ProjectRecord[]
  tasks: TaskRecord[]
  onExploreEntity: (entity: KairoGraphEntityRef) => void
}) {
  const [projectFilter, setProjectFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('open')
  const projectById = useMemo(() => new Map(projects.map((project) => [project.id, project])), [projects])
  const visible = useMemo(() => tasks.filter((task) => {
    if (projectFilter && task.project_id !== projectFilter) return false
    if (statusFilter === 'open' && ['completed', 'done', 'cancelled'].includes(task.status)) return false
    if (statusFilter !== 'all' && statusFilter !== 'open' && task.status !== statusFilter) return false
    return true
  }), [projectFilter, statusFilter, tasks])

  return (
    <div className="workspace-layout">
      <section className="workspace-main">
        <header className="workspace-title">
          <div><span className="kairo-kicker">TÂCHES</span><h1>Ce qui doit avancer</h1><p>Une vue opérationnelle simple, reliée aux mêmes projets et relations canoniques.</p></div>
          <strong>{visible.length}</strong>
        </header>

        <div className="workspace-toolbar">
          <select value={projectFilter} onChange={(event) => setProjectFilter(event.target.value)}>
            <option value="">Tous les projets</option>
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="open">Ouvertes</option>
            <option value="all">Toutes</option>
            <option value="todo">À faire</option>
            <option value="running">En cours</option>
            <option value="waiting_approval">Approbation requise</option>
            <option value="blocked">Bloquées</option>
            <option value="completed">Terminées</option>
            <option value="failed">Échecs</option>
          </select>
        </div>

        {visible.length === 0 ? (
          <div className="workspace-empty"><strong>Aucune tâche dans ce filtre.</strong><span>Les tâches créées ici apparaissent immédiatement dans le mycélium.</span></div>
        ) : (
          <div className="workspace-task-list">
            {visible.map((task) => (
              <button type="button" key={task.id} onClick={() => onExploreEntity({ entity_type: 'task', entity_id: task.id })}>
                <i className={`workspace-task-status workspace-task-status-${task.status}`} />
                <div><strong>{task.title}</strong><small>{projectById.get(task.project_id)?.name || 'Projet'} · {taskStatusLabel(task.status)}</small>{task.description && <p>{task.description}</p>}</div>
                <span>{shortDate(task.updated_at)} ›</span>
              </button>
            ))}
          </div>
        )}
      </section>
      <aside className="workspace-side"><TaskForm projects={projects} /></aside>
    </div>
  )
}

export function CoreWorkspace({
  mode,
  onExploreEntity,
}: {
  mode: CoreWorkspaceMode
  onExploreEntity: (entity: KairoGraphEntityRef) => void
}) {
  const projectsQuery = useQuery({ queryKey: ['projects'], queryFn: fetchProjects, staleTime: 8000 })
  const tasksQuery = useQuery({ queryKey: ['tasks'], queryFn: fetchTasks, staleTime: 6000 })
  const projects = projectsQuery.data || []
  const tasks = tasksQuery.data || []
  const loading = projectsQuery.isLoading || tasksQuery.isLoading
  const error = projectsQuery.error || tasksQuery.error

  if (loading) {
    return <div className="workspace-state"><span className="kairo-kicker">KAIRO</span><strong>Chargement du cockpit…</strong></div>
  }
  if (error) {
    return <div className="workspace-state workspace-state-error"><strong>Impossible de charger cet espace.</strong><span>{error instanceof Error ? error.message : 'Erreur KAIRO Core.'}</span></div>
  }

  return mode === 'projects'
    ? <ProjectsWorkspace projects={projects} tasks={tasks} onExploreEntity={onExploreEntity} />
    : <TasksWorkspace projects={projects} tasks={tasks} onExploreEntity={onExploreEntity} />
}
