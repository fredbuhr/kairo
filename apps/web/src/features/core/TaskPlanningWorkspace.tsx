import { FormEvent, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { KairoGraphEntityRef } from '@kairo/graph'

import {
  createTask,
  fetchPlanningTasks,
  fetchToday,
  updateTaskPlanning,
  type ProjectRecord,
  type TaskPlanningUpdateInput,
  type TaskRecord,
} from '../../lib/api'

type TaskView = 'today' | 'all'

const PRIORITY_LABELS = ['Plus tard', 'Basse', 'Normale', 'Haute', 'Critique']

function projectMap(projects: ProjectRecord[]) {
  return new Map(projects.map((project) => [project.id, project]))
}

function formatDateTime(value?: string | null) {
  if (!value) return null
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))
  } catch {
    return value
  }
}

function toIso(value: string) {
  return value ? new Date(value).toISOString() : null
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

function usePlanningMutation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ taskId, input }: { taskId: string; input: TaskPlanningUpdateInput }) =>
      updateTaskPlanning(taskId, input),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['planning-tasks'] }),
        client.invalidateQueries({ queryKey: ['today'] }),
        client.invalidateQueries({ queryKey: ['tasks'] }),
        client.invalidateQueries({ queryKey: ['kairo-graph'] }),
      ])
    },
  })
}

function PlanningTaskCard({
  task,
  project,
  onExplore,
}: {
  task: TaskRecord
  project?: ProjectRecord
  onExplore: (entity: KairoGraphEntityRef) => void
}) {
  const mutation = usePlanningMutation()
  const [editing, setEditing] = useState(false)
  const [priority, setPriority] = useState(task.priority ?? 2)
  const [dueAt, setDueAt] = useState(task.due_at ? new Date(task.due_at).toISOString().slice(0, 16) : '')
  const [startAt, setStartAt] = useState(task.planned_start_at ? new Date(task.planned_start_at).toISOString().slice(0, 16) : '')
  const [endAt, setEndAt] = useState(task.planned_end_at ? new Date(task.planned_end_at).toISOString().slice(0, 16) : '')

  const dueLabel = formatDateTime(task.due_at)
  const planLabel = formatDateTime(task.planned_start_at)

  function savePlanning(event: FormEvent) {
    event.preventDefault()
    mutation.mutate({
      taskId: task.id,
      input: {
        priority,
        due_at: toIso(dueAt),
        planned_start_at: toIso(startAt),
        planned_end_at: toIso(endAt),
      },
    }, { onSuccess: () => setEditing(false) })
  }

  function setStatus(status: string) {
    mutation.mutate({ taskId: task.id, input: { status } })
  }

  return (
    <article className={`planning-task planning-task-priority-${task.priority ?? 2}`}>
      <button
        type="button"
        className={`planning-check ${['completed', 'done'].includes(task.status) ? 'planning-check-done' : ''}`}
        onClick={() => setStatus(['completed', 'done'].includes(task.status) ? 'todo' : 'completed')}
        aria-label={['completed', 'done'].includes(task.status) ? 'Rouvrir la tâche' : 'Terminer la tâche'}
      >
        {['completed', 'done'].includes(task.status) ? '✓' : ''}
      </button>
      <div className="planning-task-body">
        <div className="planning-task-topline">
          <strong>{task.title}</strong>
          <span>{PRIORITY_LABELS[task.priority ?? 2]}</span>
        </div>
        <small>{project?.name || 'Projet'} · {taskStatusLabel(task.status)}</small>
        {task.description && <p>{task.description}</p>}
        <div className="planning-task-time">
          {dueLabel && <span className="planning-due">Échéance {dueLabel}</span>}
          {planLabel && <span>Prévu {planLabel}</span>}
        </div>
        {editing && (
          <form className="planning-editor" onSubmit={savePlanning}>
            <label><span>Priorité</span><select value={priority} onChange={(event) => setPriority(Number(event.target.value))}>{PRIORITY_LABELS.map((label, index) => <option key={label} value={index}>{label}</option>)}</select></label>
            <label><span>Début prévu</span><input type="datetime-local" value={startAt} onChange={(event) => setStartAt(event.target.value)} /></label>
            <label><span>Fin prévue</span><input type="datetime-local" value={endAt} onChange={(event) => setEndAt(event.target.value)} /></label>
            <label><span>Échéance</span><input type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} /></label>
            <div className="planning-editor-actions"><button type="button" onClick={() => setEditing(false)}>Annuler</button><button type="submit" disabled={mutation.isPending}>Enregistrer</button></div>
            {mutation.isError && <small className="workspace-error">{mutation.error instanceof Error ? mutation.error.message : 'Mise à jour impossible.'}</small>}
          </form>
        )}
      </div>
      <div className="planning-task-actions">
        {!['running', 'in_progress', 'completed', 'done'].includes(task.status) && <button type="button" onClick={() => setStatus('in_progress')}>Démarrer</button>}
        <button type="button" onClick={() => setEditing((value) => !value)}>Planifier</button>
        <button type="button" onClick={() => onExplore({ entity_type: 'task', entity_id: task.id })}>Cerveau ↗</button>
      </div>
    </article>
  )
}

function TodayGroup({
  title,
  hint,
  tasks,
  projects,
  onExplore,
}: {
  title: string
  hint: string
  tasks: TaskRecord[]
  projects: Map<string, ProjectRecord>
  onExplore: (entity: KairoGraphEntityRef) => void
}) {
  if (tasks.length === 0) return null
  return (
    <section className="today-group">
      <header><div><strong>{title}</strong><span>{hint}</span></div><b>{tasks.length}</b></header>
      <div className="planning-task-list">
        {tasks.map((task) => <PlanningTaskCard key={task.id} task={task} project={projects.get(task.project_id)} onExplore={onExplore} />)}
      </div>
    </section>
  )
}

function NewPlannedTask({ projects }: { projects: ProjectRecord[] }) {
  const client = useQueryClient()
  const [projectId, setProjectId] = useState(projects[0]?.id || '')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState(2)
  const [dueAt, setDueAt] = useState('')
  const [plannedStartAt, setPlannedStartAt] = useState('')
  const [plannedEndAt, setPlannedEndAt] = useState('')
  const mutation = useMutation({
    mutationFn: async () => {
      const task = await createTask({
        project_id: projectId,
        title: title.trim(),
        description: description.trim() || null,
      })
      if (priority !== 2 || dueAt || plannedStartAt || plannedEndAt) {
        return updateTaskPlanning(task.id, {
          priority,
          due_at: toIso(dueAt),
          planned_start_at: toIso(plannedStartAt),
          planned_end_at: toIso(plannedEndAt),
        })
      }
      return task
    },
    onSuccess: async () => {
      setTitle('')
      setDescription('')
      setPriority(2)
      setDueAt('')
      setPlannedStartAt('')
      setPlannedEndAt('')
      await Promise.all([
        client.invalidateQueries({ queryKey: ['planning-tasks'] }),
        client.invalidateQueries({ queryKey: ['today'] }),
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
    <form className="workspace-create planned-task-create" onSubmit={submit}>
      <div className="workspace-create-heading"><div><span className="kairo-kicker">NOUVELLE</span><strong>Créer et planifier</strong></div><button type="submit" disabled={!projectId || !title.trim() || mutation.isPending}>{mutation.isPending ? 'Création…' : 'Créer'}</button></div>
      <select value={projectId} onChange={(event) => setProjectId(event.target.value)}><option value="">Choisir un projet</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
      <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Titre de la tâche" maxLength={320} />
      <textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description optionnelle" rows={2} />
      <label><span>Priorité</span><select value={priority} onChange={(event) => setPriority(Number(event.target.value))}>{PRIORITY_LABELS.map((label, index) => <option key={label} value={index}>{label}</option>)}</select></label>
      <label><span>Début prévu</span><input type="datetime-local" value={plannedStartAt} onChange={(event) => setPlannedStartAt(event.target.value)} /></label>
      <label><span>Fin prévue</span><input type="datetime-local" value={plannedEndAt} onChange={(event) => setPlannedEndAt(event.target.value)} /></label>
      <label><span>Échéance</span><input type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} /></label>
      {mutation.isError && <small className="workspace-error">{mutation.error instanceof Error ? mutation.error.message : 'Création impossible.'}</small>}
    </form>
  )
}

export function TaskPlanningWorkspace({
  projects,
  onExploreEntity,
}: {
  projects: ProjectRecord[]
  onExploreEntity: (entity: KairoGraphEntityRef) => void
}) {
  const [view, setView] = useState<TaskView>('today')
  const [projectFilter, setProjectFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('open')
  const projectById = useMemo(() => projectMap(projects), [projects])
  const planningQuery = useQuery({
    queryKey: ['planning-tasks', true],
    queryFn: () => fetchPlanningTasks(true),
    staleTime: 5000,
  })
  const todayQuery = useQuery({
    queryKey: ['today'],
    queryFn: fetchToday,
    staleTime: 30000,
    refetchInterval: 60000,
  })
  const allTasks = planningQuery.data || []
  const visible = useMemo(() => allTasks.filter((task) => {
    if (projectFilter && task.project_id !== projectFilter) return false
    if (statusFilter === 'open' && ['completed', 'done', 'cancelled'].includes(task.status)) return false
    if (statusFilter !== 'all' && statusFilter !== 'open' && task.status !== statusFilter) return false
    return true
  }), [allTasks, projectFilter, statusFilter])
  const today = todayQuery.data
  const todayCount = (today?.overdue.length || 0) + (today?.due_today.length || 0) + (today?.planned_today.length || 0) + (today?.important.length || 0)

  if (planningQuery.isLoading || todayQuery.isLoading) {
    return <div className="workspace-state"><span className="kairo-kicker">TÂCHES</span><strong>Construction de votre journée…</strong></div>
  }
  const error = planningQuery.error || todayQuery.error
  if (error) {
    return <div className="workspace-state workspace-state-error"><strong>Impossible de lire la planification.</strong><span>{error instanceof Error ? error.message : 'Erreur KAIRO Core.'}</span></div>
  }

  return (
    <div className="workspace-layout task-planning-workspace">
      <section className="workspace-main">
        <header className="workspace-title">
          <div><span className="kairo-kicker">TÂCHES</span><h1>{view === 'today' ? 'Aujourd’hui' : 'Toutes les tâches'}</h1><p>Priorités, échéances et créneaux sont des données KAIRO explicites — jamais une priorité inventée par l’interface.</p></div>
          <strong>{view === 'today' ? todayCount : visible.length}</strong>
        </header>
        <div className="planning-tabs">
          <button type="button" className={view === 'today' ? 'planning-tab-active' : ''} onClick={() => setView('today')}>Aujourd’hui <span>{todayCount}</span></button>
          <button type="button" className={view === 'all' ? 'planning-tab-active' : ''} onClick={() => setView('all')}>Toutes</button>
        </div>

        {view === 'today' ? (
          <div className="today-groups">
            {todayCount === 0 && <div className="workspace-empty"><strong>Rien d’explicite pour aujourd’hui.</strong><span>Ajoutez une échéance, un créneau ou une priorité haute à une tâche pour la faire apparaître ici.</span></div>}
            <TodayGroup title="En retard" hint="échéance dépassée" tasks={today?.overdue || []} projects={projectById} onExplore={onExploreEntity} />
            <TodayGroup title="À échéance aujourd’hui" hint="due aujourd’hui" tasks={today?.due_today || []} projects={projectById} onExplore={onExploreEntity} />
            <TodayGroup title="Prévu aujourd’hui" hint="créneau planifié" tasks={today?.planned_today || []} projects={projectById} onExplore={onExploreEntity} />
            <TodayGroup title="Important" hint="priorité haute sans créneau aujourd’hui" tasks={today?.important || []} projects={projectById} onExplore={onExploreEntity} />
          </div>
        ) : (
          <>
            <div className="workspace-toolbar">
              <select value={projectFilter} onChange={(event) => setProjectFilter(event.target.value)}><option value="">Tous les projets</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="open">Ouvertes</option><option value="all">Toutes</option><option value="todo">À faire</option><option value="in_progress">En cours</option><option value="waiting_approval">Approbation requise</option><option value="blocked">Bloquées</option><option value="completed">Terminées</option><option value="failed">Échecs</option></select>
            </div>
            {visible.length === 0 ? <div className="workspace-empty"><strong>Aucune tâche dans ce filtre.</strong></div> : <div className="planning-task-list">{visible.map((task) => <PlanningTaskCard key={task.id} task={task} project={projectById.get(task.project_id)} onExplore={onExploreEntity} />)}</div>}
          </>
        )}
      </section>
      <aside className="workspace-side"><NewPlannedTask projects={projects} /></aside>
    </div>
  )
}
