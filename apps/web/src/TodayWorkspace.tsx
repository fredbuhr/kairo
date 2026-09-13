import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { nevoliumFetch } from './lib/apiClient'

type PlannedTask = {
  id: string
  project_id: string
  title: string
  description?: string | null
  status: string
  priority: number
  planned_start_at?: string | null
  planned_end_at?: string | null
  due_at?: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

type TodayBucket =
  | 'overdue'
  | 'in_progress'
  | 'due_today'
  | 'planned'
  | 'completed_today'
  | 'backlog'

type TodayTaskItem = {
  bucket: TodayBucket
  project_id: string
  project_name: string
  task: PlannedTask
}

type TodayView = {
  next_cursors?: Partial<Record<TodayBucket, string>>
  day: string
  timezone: string
  day_start: string
  day_end: string
  overdue: TodayTaskItem[]
  in_progress: TodayTaskItem[]
  due_today: TodayTaskItem[]
  planned: TodayTaskItem[]
  completed_today: TodayTaskItem[]
  backlog: TodayTaskItem[]
}

type Props = {
  apiUrl: string
}

const BUCKETS: Array<{
  key: TodayBucket
  title: string
  hint: string
}> = [
  { key: 'overdue', title: 'En retard', hint: 'Échéance antérieure à aujourd’hui' },
  { key: 'in_progress', title: 'En cours', hint: 'Travail déjà confié à Nevolium / Temporal' },
  { key: 'due_today', title: 'À rendre aujourd’hui', hint: 'Échéance dans la journée' },
  { key: 'planned', title: 'Planifié aujourd’hui', hint: 'Créneau de travail qui recouvre la journée' },
  { key: 'completed_today', title: 'Terminé aujourd’hui', hint: 'Actions clôturées pendant la journée' },
  { key: 'backlog', title: 'À organiser', hint: 'Tâches à faire sans date ni créneau' },
]

const PRIORITY_LABELS = ['P0 · basse', 'P1', 'P2 · normale', 'P3', 'P4 · haute']

async function readJson<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    const message = typeof detail === 'string' ? detail : detail?.message
    throw new Error(message || `Nevolium Core répond ${response.status}`)
  }
  return body as T
}

function localIsoDay(timezone: string, value = new Date()) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(value)
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}

function formatDateTime(value?: string | null) {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed)
}

function timingLabel(task: PlannedTask) {
  const due = formatDateTime(task.due_at)
  const plannedStart = formatDateTime(task.planned_start_at)
  const plannedEnd = formatDateTime(task.planned_end_at)
  if (due) return `Échéance · ${due}`
  if (plannedStart && plannedEnd) return `Planifié · ${plannedStart} → ${plannedEnd}`
  if (plannedStart) return `Planifié · ${plannedStart}`
  return 'Sans date'
}

export default function TodayWorkspace({ apiUrl }: Props) {
  const timezone = useMemo(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
    [],
  )
  const [day, setDay] = useState(() => localIsoDay(timezone))
  const [view, setView] = useState<TodayView | null>(null)
  const [loading, setLoading] = useState(true)
  const [savingTaskId, setSavingTaskId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const generation = useRef(0)
  const requests = useRef(new Set<AbortController>())
  const [loadingBucket, setLoadingBucket] = useState<TodayBucket | null>(null)
  const currentDay = useRef(day)
  currentDay.current = day

  const load = useCallback(async () => {
    if (currentDay.current !== day) return
    const version = ++generation.current
    for (const pending of requests.current) pending.abort()
    requests.current.clear()
    const controller = new AbortController()
    requests.current.add(controller)
    setLoading(true)
    setLoadingBucket(null)
    setError(null)
    try {
      const response = await nevoliumFetch(
        `${apiUrl}/v1/today?day=${encodeURIComponent(day)}&timezone=${encodeURIComponent(timezone)}`,
        { signal: controller.signal },
      )
      const result = await readJson<TodayView>(response)
      if (version === generation.current && currentDay.current === day) setView(result)
    } catch (loadError) {
      if (!controller.signal.aborted && version === generation.current) setError(loadError instanceof Error ? loadError.message : 'Impossible de charger Today.')
    } finally {
      requests.current.delete(controller)
      if (version === generation.current) setLoading(false)
    }
  }, [apiUrl, day, timezone])

  useEffect(() => {
    setView(null)
    void load()
    return () => { ++generation.current; for (const pending of requests.current) pending.abort() }
  }, [load])

  async function loadBucket(bucket: TodayBucket) {
    const cursor = view?.next_cursors?.[bucket]
    if (!cursor || loading || loadingBucket) return
    const version = generation.current
    const controller = new AbortController()
    requests.current.add(controller)
    setLoadingBucket(bucket)
    setError(null)
    try {
      const response = await nevoliumFetch(
        `${apiUrl}/v1/today?day=${encodeURIComponent(day)}&timezone=${encodeURIComponent(timezone)}&bucket=${bucket}&cursor=${encodeURIComponent(cursor)}`,
        { signal: controller.signal },
      )
      const page = await readJson<TodayView>(response)
      if (version !== generation.current || currentDay.current !== day) return
      setView((current) => {
        if (!current || current.day !== page.day) return current
        const rows = new Map(current[bucket].map((item) => [item.task.id, item]))
        for (const item of page[bucket]) rows.set(item.task.id, item)
        return { ...current, [bucket]: [...rows.values()],
          next_cursors: { ...current.next_cursors, [bucket]: page.next_cursors?.[bucket] } }
      })
    } catch (cause) {
      if (!controller.signal.aborted && version === generation.current) setError(cause instanceof Error ? cause.message : 'Chargement impossible.')
    } finally {
      requests.current.delete(controller)
      if (version === generation.current) setLoadingBucket(null)
    }
  }

  async function updateTask(taskId: string, payload: Record<string, unknown>) {
    setSavingTaskId(taskId)
    setError(null)
    try {
      const response = await nevoliumFetch(`${apiUrl}/v1/tasks/${taskId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      await readJson<PlannedTask>(response)
      await load()
    } catch (updateError) {
      setError(
        updateError instanceof Error ? updateError.message : 'Impossible de mettre à jour la tâche.',
      )
    } finally {
      setSavingTaskId(null)
    }
  }

  function planFromNow(taskId: string) {
    const start = new Date()
    const end = new Date(start.getTime() + 60 * 60 * 1000)
    void updateTask(taskId, {
      planned_start_at: start.toISOString(),
      planned_end_at: end.toISOString(),
    })
  }

  const total = view
    ? BUCKETS.reduce((count, bucket) => count + view[bucket.key].length, 0)
    : 0

  return (
    <section className="news-workspace" aria-labelledby="today-heading">
      <div className="news-heading">
        <div>
          <span className="eyebrow">TODAY</span>
          <h2 id="today-heading">Votre journée sur le même modèle Task que Projects et le futur Gantt.</h2>
        </div>
        <span className="run-state">{total} tâche(s) affichée(s)</span>
      </div>

      <div className="news-controls">
        <label>
          <span>Journée</span>
          <input type="date" value={day} onChange={(event) => setDay(event.target.value)} />
        </label>
        <div>
          <span className="eyebrow">FUSEAU</span>
          <small>{timezone}</small>
        </div>
        <button type="button" disabled={loading} onClick={() => void load()}>
          {loading ? 'Actualisation…' : 'Actualiser'}
        </button>
      </div>

      {error && <div className="error-panel">{error}</div>}
      {loading && !view && !error && (
        <div className="progress-panel">
          <strong>Composition de votre journée.</strong>
          <span>Nevolium agrège uniquement les Tasks du propriétaire authentifié.</span>
        </div>
      )}

      {!loading && view && total === 0 && !error && (
        <div className="progress-panel">
          <strong>Aucune tâche pour cette journée.</strong>
          <span>Ajoutez une tâche dans Projects ou choisissez une autre date.</span>
        </div>
      )}

      {view && (
        <div className="sources">
          {BUCKETS.map((bucket) => {
            const items = view[bucket.key]
            if (items.length === 0) return null
            return (
              <section key={bucket.key} aria-label={bucket.title}>
                <div className="sources-title">
                  <div>
                    <strong>{bucket.title}</strong>
                    <small style={{ display: 'block' }}>{bucket.hint}</small>
                  </div>
                  <span>{items.length} affichée(s)</span>
                  {view.next_cursors?.[bucket.key] && <button type="button" disabled={loading || Boolean(loadingBucket)} onClick={() => void loadBucket(bucket.key)}>Charger la suite</button>}
                </div>
                <div className="source-list">
                  {items.map(({ task, project_name: projectName }) => {
                    const saving = savingTaskId === task.id
                    const workflowManaged = ['queued', 'running'].includes(task.status)
                    return (
                      <article className="source-card" key={task.id}>
                        <span className="source-id">P{task.priority}</span>
                        <div style={{ width: '100%' }}>
                          <strong>{task.title}</strong>
                          <small>{projectName} · {timingLabel(task)}</small>
                          {task.description && <small>{task.description}</small>}
                          <div
                            className="news-controls"
                            style={{ marginTop: 8, alignItems: 'end' }}
                          >
                            <label>
                              <span>Priorité</span>
                              <select
                                value={task.priority}
                                disabled={saving}
                                onChange={(event) =>
                                  void updateTask(task.id, { priority: Number(event.target.value) })
                                }
                              >
                                {PRIORITY_LABELS.map((label, priority) => (
                                  <option key={label} value={priority}>
                                    {label}
                                  </option>
                                ))}
                              </select>
                            </label>

                            {bucket.key === 'backlog' && (
                              <button type="button" disabled={saving} onClick={() => planFromNow(task.id)}>
                                Planifier 1 h
                              </button>
                            )}

                            {!workflowManaged && task.status !== 'completed' && (
                              <button
                                type="button"
                                disabled={saving}
                                onClick={() => void updateTask(task.id, { status: 'completed' })}
                              >
                                Terminer
                              </button>
                            )}
                            {task.status === 'completed' && (
                              <button
                                type="button"
                                disabled={saving}
                                onClick={() => void updateTask(task.id, { status: 'todo' })}
                              >
                                Réouvrir
                              </button>
                            )}
                            {workflowManaged && (
                              <small>Statut piloté par Temporal</small>
                            )}
                          </div>
                        </div>
                      </article>
                    )
                  })}
                </div>
              </section>
            )
          })}
        </div>
      )}
    </section>
  )
}
