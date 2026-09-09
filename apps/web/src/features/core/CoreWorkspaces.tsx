import { FormEvent, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { KairoGraphEntityRef } from '@kairo/graph'

import {
  createProject,
  fetchPlanningTasks,
  fetchProjects,
  updateProject,
  type ProjectRecord,
  type TaskRecord,
} from '../../lib/api'
import { AgentsWorkspace } from './AgentsWorkspace'
import { AutomationsWorkspace } from './AutomationsWorkspace'
import { CalendarWorkspace } from './CalendarWorkspace'
import { FinanceWorkspace } from './FinanceWorkspace'
import { KnowledgeWorkspace } from './KnowledgeWorkspace'
import { TaskPlanningWorkspace } from './TaskPlanningWorkspace'
import { ToolsWorkspace } from './ToolsWorkspace'

export type CoreWorkspaceMode = 'projects' | 'tasks' | 'knowledge' | 'calendar' | 'agents' | 'automations' | 'finance' | 'tools'

function shortDate(value: string) {
  try {
    return new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short' }).format(new Date(value))
  } catch {
    return value
  }
}

function projectStatusLabel(status: string) {
  const labels: Record<string, string> = {
    active: 'Actif',
    paused: 'En pause',
    archived: 'Archivé',
  }
  return labels[status] || status
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
        {projects.filter((project) => project.status !== 'archived').map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
      </select>
      {mutation.isError && <small className="workspace-error">{mutation.error instanceof Error ? mutation.error.message : 'Création impossible.'}</small>}
    </form>
  )
}

function ProjectCard({
  project,
  projects,
  counts,
  onExploreEntity,
}: {
  project: ProjectRecord
  projects: ProjectRecord[]
  counts: { open: number; total: number }
  onExploreEntity: (entity: KairoGraphEntityRef) => void
}) {
  const client = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(project.name)
  const [summary, setSummary] = useState(project.summary || '')
  const [status, setStatus] = useState(project.status)
  const [parentId, setParentId] = useState(project.parent_id || '')
  const mutation = useMutation({
    mutationFn: () => updateProject(project.id, {
      name: name.trim(),
      summary: summary.trim() || null,
      status,
      parent_id: parentId || null,
    }),
    onSuccess: async () => {
      setEditing(false)
      await Promise.all([
        client.invalidateQueries({ queryKey: ['projects'] }),
        client.invalidateQueries({ queryKey: ['planning-tasks'] }),
        client.invalidateQueries({ queryKey: ['kairo-graph'] }),
      ])
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim() || mutation.isPending) return
    mutation.mutate()
  }

  function cancel() {
    setName(project.name)
    setSummary(project.summary || '')
    setStatus(project.status)
    setParentId(project.parent_id || '')
    setEditing(false)
  }

  return (
    <article className={`workspace-project-card ${project.status === 'archived' ? 'workspace-project-card-archived' : ''}`}>
      <div className="workspace-project-topline"><span>{projectStatusLabel(project.status)}</span><small>{shortDate(project.updated_at)}</small></div>
      {!editing ? (
        <>
          <h2>{project.name}</h2>
          <p>{project.summary || 'Aucun résumé.'}</p>
          <div className="workspace-project-metrics"><span><strong>{counts.open}</strong> ouvertes</span><span><strong>{counts.total}</strong> tâches</span></div>
          <div className="workspace-project-actions">
            <button type="button" onClick={() => onExploreEntity({ entity_type: 'project', entity_id: project.id })}>Explorer</button>
            <button type="button" onClick={() => setEditing(true)}>Modifier</button>
          </div>
        </>
      ) : (
        <form className="workspace-project-editor" onSubmit={submit}>
          <input value={name} onChange={(event) => setName(event.target.value)} maxLength={240} aria-label="Nom du projet" />
          <textarea value={summary} onChange={(event) => setSummary(event.target.value)} rows={3} placeholder="Résumé" />
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="active">Actif</option>
            <option value="paused">En pause</option>
            <option value="archived">Archivé</option>
          </select>
          <select value={parentId} onChange={(event) => setParentId(event.target.value)}>
            <option value="">Aucun projet parent</option>
            {projects.filter((candidate) => candidate.id !== project.id && candidate.status !== 'archived').map((candidate) => (
              <option key={candidate.id} value={candidate.id}>{candidate.name}</option>
            ))}
          </select>
          <div className="workspace-project-actions">
            <button type="button" onClick={cancel}>Annuler</button>
            <button type="submit" disabled={!name.trim() || mutation.isPending}>{mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}</button>
          </div>
          {mutation.isError && <small className="workspace-error">{mutation.error instanceof Error ? mutation.error.message : 'Mise à jour impossible.'}</small>}
        </form>
      )}
    </article>
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

  const activeCount = projects.filter((project) => project.status !== 'archived').length

  return (
    <div className="workspace-layout">
      <section className="workspace-main">
        <header className="workspace-title">
          <div><span className="kairo-kicker">PROJETS</span><h1>Vos projets</h1><p>La même réalité canonique que dans le mycélium, présentée ici pour travailler plus directement.</p></div>
          <strong>{activeCount}</strong>
        </header>

        {projects.length === 0 ? (
          <div className="workspace-empty"><strong>Aucun projet pour l’instant.</strong><span>Créez votre premier projet : il apparaîtra aussi dans le cerveau KAIRO.</span></div>
        ) : (
          <div className="workspace-project-grid">
            {projects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                projects={projects}
                counts={taskCounts.get(project.id) || { open: 0, total: 0 }}
                onExploreEntity={onExploreEntity}
              />
            ))}
          </div>
        )}
      </section>
      <aside className="workspace-side"><ProjectForm projects={projects} /></aside>
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
  const requiresProjects = mode !== 'tools'
  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: fetchProjects,
    staleTime: 8000,
    enabled: requiresProjects,
  })
  const projectTasksQuery = useQuery({
    queryKey: ['planning-tasks', true],
    queryFn: () => fetchPlanningTasks(true),
    staleTime: 6000,
    enabled: mode === 'projects',
  })

  if (mode === 'tools') {
    return <ToolsWorkspace />
  }

  const projects = projectsQuery.data || []
  const tasks = projectTasksQuery.data || []
  const loading = projectsQuery.isLoading || (mode === 'projects' && projectTasksQuery.isLoading)
  const error = projectsQuery.error || (mode === 'projects' ? projectTasksQuery.error : null)

  if (loading) {
    return <div className="workspace-state"><span className="kairo-kicker">KAIRO</span><strong>Chargement du cockpit…</strong></div>
  }
  if (error) {
    return <div className="workspace-state workspace-state-error"><strong>Impossible de charger cet espace.</strong><span>{error instanceof Error ? error.message : 'Erreur KAIRO Core.'}</span></div>
  }

  if (mode === 'knowledge') {
    return <KnowledgeWorkspace projects={projects} onExploreEntity={onExploreEntity} />
  }
  if (mode === 'tasks') {
    return <TaskPlanningWorkspace projects={projects} onExploreEntity={onExploreEntity} />
  }
  if (mode === 'calendar') {
    return <CalendarWorkspace projects={projects} onExploreEntity={onExploreEntity} />
  }
  if (mode === 'agents') {
    return <AgentsWorkspace projects={projects} onExploreEntity={onExploreEntity} />
  }
  if (mode === 'automations') {
    return <AutomationsWorkspace projects={projects} onExploreEntity={onExploreEntity} />
  }
  if (mode === 'finance') {
    return <FinanceWorkspace projects={projects} />
  }
  return <ProjectsWorkspace projects={projects} tasks={tasks} onExploreEntity={onExploreEntity} />
}
