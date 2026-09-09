import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { KairoGraphEntityRef } from '@kairo/graph'

import { fetchPlanningTasks, type ProjectRecord, type TaskRecord } from '../../lib/api'

const DAY_MS = 86_400_000
const CALENDAR_START_HOUR = 6
const CALENDAR_END_HOUR = 22

function startOfWeek(value: Date) {
  const date = new Date(value.getFullYear(), value.getMonth(), value.getDate())
  const weekday = (date.getDay() + 6) % 7
  date.setDate(date.getDate() - weekday)
  return date
}

function addDays(value: Date, days: number) {
  const date = new Date(value)
  date.setDate(date.getDate() + days)
  return date
}

function dayKey(value: Date) {
  return `${value.getFullYear()}-${value.getMonth()}-${value.getDate()}`
}

function sameDay(a: Date, b: Date) {
  return dayKey(a) === dayKey(b)
}

function formatDay(value: Date) {
  return new Intl.DateTimeFormat('fr-FR', { weekday: 'short', day: '2-digit', month: 'short' }).format(value)
}

function formatWeek(value: Date) {
  const end = addDays(value, 6)
  return `${new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short' }).format(value)} — ${new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }).format(end)}`
}

function overlapsDay(task: TaskRecord, day: Date) {
  if (!task.planned_start_at) return false
  const start = new Date(task.planned_start_at)
  const end = task.planned_end_at ? new Date(task.planned_end_at) : start
  const dayStart = new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime()
  const dayEnd = dayStart + DAY_MS
  return start.getTime() < dayEnd && end.getTime() >= dayStart
}

function eventGeometry(task: TaskRecord, day: Date) {
  const start = new Date(task.planned_start_at!)
  const end = task.planned_end_at ? new Date(task.planned_end_at) : new Date(start.getTime() + 45 * 60_000)
  const dayStart = new Date(day.getFullYear(), day.getMonth(), day.getDate(), CALENDAR_START_HOUR).getTime()
  const dayEnd = new Date(day.getFullYear(), day.getMonth(), day.getDate(), CALENDAR_END_HOUR).getTime()
  const visibleStart = Math.max(start.getTime(), dayStart)
  const visibleEnd = Math.min(Math.max(end.getTime(), visibleStart + 30 * 60_000), dayEnd)
  const duration = Math.max(1, dayEnd - dayStart)
  const top = Math.max(0, Math.min(100, (visibleStart - dayStart) / duration * 100))
  const height = Math.max(2.8, Math.min(100 - top, (visibleEnd - visibleStart) / duration * 100))
  return { top, height, clippedStart: start.getTime() < dayStart, clippedEnd: end.getTime() > dayEnd }
}

function timeLabel(value: string) {
  return new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

export function CalendarWorkspace({
  projects,
  onExploreEntity,
}: {
  projects: ProjectRecord[]
  onExploreEntity: (entity: KairoGraphEntityRef) => void
}) {
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()))
  const [projectFilter, setProjectFilter] = useState('')
  const tasksQuery = useQuery({
    queryKey: ['planning-tasks', true],
    queryFn: () => fetchPlanningTasks(true),
    staleTime: 5000,
  })
  const projectsById = useMemo(() => new Map(projects.map((project) => [project.id, project])), [projects])
  const days = useMemo(() => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)), [weekStart])
  const openTasks = useMemo(
    () => (tasksQuery.data || []).filter((task) => !['completed', 'done', 'cancelled'].includes(task.status) && (!projectFilter || task.project_id === projectFilter)),
    [projectFilter, tasksQuery.data],
  )
  const now = new Date()

  if (tasksQuery.isLoading) {
    return <div className="workspace-state"><span className="kairo-kicker">CALENDRIER</span><strong>Construction de la semaine…</strong></div>
  }
  if (tasksQuery.isError) {
    return <div className="workspace-state workspace-state-error"><strong>Impossible de lire le calendrier KAIRO.</strong><span>{tasksQuery.error instanceof Error ? tasksQuery.error.message : 'Erreur KAIRO Core.'}</span></div>
  }

  return (
    <div className="calendar-workspace">
      <header className="calendar-workspace-header">
        <div>
          <span className="kairo-kicker">CALENDRIER</span>
          <h1>{formatWeek(weekStart)}</h1>
          <p>Vue hebdomadaire des créneaux et échéances explicites des tâches KAIRO. Les calendriers externes viendront s’ajouter avec leur provenance, sans remplacer ces faits.</p>
        </div>
        <div className="calendar-controls">
          <div><button type="button" onClick={() => setWeekStart((value) => addDays(value, -7))}>←</button><button type="button" onClick={() => setWeekStart(startOfWeek(new Date()))}>Aujourd’hui</button><button type="button" onClick={() => setWeekStart((value) => addDays(value, 7))}>→</button></div>
          <select value={projectFilter} onChange={(event) => setProjectFilter(event.target.value)}><option value="">Tous les projets</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
        </div>
      </header>

      <div className="calendar-week">
        <div className="calendar-time-header" />
        {days.map((day) => <div key={dayKey(day)} className={`calendar-day-header ${sameDay(day, now) ? 'calendar-day-today' : ''}`}><strong>{formatDay(day)}</strong><span>{openTasks.filter((task) => overlapsDay(task, day) || (task.due_at && sameDay(new Date(task.due_at), day))).length}</span></div>)}

        <div className="calendar-time-axis">
          {Array.from({ length: CALENDAR_END_HOUR - CALENDAR_START_HOUR + 1 }, (_, index) => CALENDAR_START_HOUR + index).map((hour) => <span key={hour} style={{ top: `${(hour - CALENDAR_START_HOUR) / (CALENDAR_END_HOUR - CALENDAR_START_HOUR) * 100}%` }}>{String(hour).padStart(2, '0')}:00</span>)}
        </div>

        {days.map((day) => {
          const scheduled = openTasks.filter((task) => overlapsDay(task, day))
          const deadlines = openTasks.filter((task) => !task.planned_start_at && task.due_at && sameDay(new Date(task.due_at), day))
          return (
            <div key={`body:${dayKey(day)}`} className={`calendar-day-column ${sameDay(day, now) ? 'calendar-day-column-today' : ''}`}>
              {Array.from({ length: CALENDAR_END_HOUR - CALENDAR_START_HOUR + 1 }, (_, index) => <i key={index} style={{ top: `${index / (CALENDAR_END_HOUR - CALENDAR_START_HOUR) * 100}%` }} />)}
              {scheduled.map((task) => {
                const geometry = eventGeometry(task, day)
                return (
                  <button
                    type="button"
                    key={task.id}
                    className={`calendar-event calendar-event-priority-${task.priority ?? 2}`}
                    style={{ top: `${geometry.top}%`, height: `${geometry.height}%` }}
                    onClick={() => onExploreEntity({ entity_type: 'task', entity_id: task.id })}
                    title={`${task.title} · ${timeLabel(task.planned_start_at!)}${task.planned_end_at ? `–${timeLabel(task.planned_end_at)}` : ''}`}
                  >
                    <strong>{task.title}</strong>
                    <small>{geometry.clippedStart ? '…' : timeLabel(task.planned_start_at!)}{task.planned_end_at ? ` — ${geometry.clippedEnd ? '…' : timeLabel(task.planned_end_at)}` : ''}</small>
                    <span>{projectsById.get(task.project_id)?.name || 'Projet'}</span>
                  </button>
                )
              })}
              {deadlines.length > 0 && (
                <div className="calendar-deadlines">
                  {deadlines.map((task) => <button type="button" key={task.id} onClick={() => onExploreEntity({ entity_type: 'task', entity_id: task.id })}><i /> <span>{timeLabel(task.due_at!)} · {task.title}</span></button>)}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
