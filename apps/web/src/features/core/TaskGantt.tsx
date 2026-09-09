import { useMemo, useState } from 'react'
import type { KairoGraphEntityRef } from '@kairo/graph'
import {
  buildGanttTicks,
  buildGanttWindow,
  projectGanttItems,
  type CanonicalPlanningTask,
  type GanttWindow,
} from '@kairo/gantt'

import type { ProjectRecord, TaskRecord } from '../../lib/api'

type ScaleDays = 14 | 30 | 90

function taskSource(task: TaskRecord): CanonicalPlanningTask {
  return {
    taskId: task.id,
    title: task.title,
    projectId: task.project_id,
    plannedStart: task.planned_start_at,
    plannedEnd: task.planned_end_at,
    dueAt: task.due_at,
    priority: task.priority ?? 2,
    status: task.status,
  }
}

function dateLabel(value?: string | null) {
  if (!value) return null
  try {
    return new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short' }).format(new Date(value))
  } catch {
    return value
  }
}

function duePosition(value: string | null | undefined, window: GanttWindow) {
  if (!value) return null
  const time = new Date(value).getTime()
  if (!Number.isFinite(time) || time < window.startMs || time > window.endMs) return null
  return (time - window.startMs) / Math.max(1, window.endMs - window.startMs) * 100
}

function moveAnchor(anchor: Date, days: number) {
  const next = new Date(anchor)
  next.setDate(next.getDate() + days)
  return next
}

export function TaskGantt({
  tasks,
  projects,
  onExploreEntity,
}: {
  tasks: TaskRecord[]
  projects: Map<string, ProjectRecord>
  onExploreEntity: (entity: KairoGraphEntityRef) => void
}) {
  const [scale, setScale] = useState<ScaleDays>(30)
  const [anchor, setAnchor] = useState(() => new Date())
  const [projectFilter, setProjectFilter] = useState('')
  const window = useMemo(() => buildGanttWindow(anchor, scale), [anchor, scale])
  const ticks = useMemo(() => buildGanttTicks(window), [window])
  const filteredTasks = useMemo(
    () => tasks.filter((task) => !projectFilter || task.project_id === projectFilter),
    [projectFilter, tasks],
  )
  const items = useMemo(
    () => projectGanttItems(filteredTasks.map(taskSource), window),
    [filteredTasks, window],
  )
  const itemTaskIds = useMemo(() => new Set(items.map((item) => item.taskId)), [items])
  const taskById = useMemo(() => new Map(filteredTasks.map((task) => [task.id, task])), [filteredTasks])
  const visibleTicks = useMemo(() => {
    const stride = scale === 14 ? 1 : scale === 30 ? 2 : 7
    return ticks.filter((_, index) => index % stride === 0 || index === ticks.length - 1)
  }, [scale, ticks])
  const unscheduled = filteredTasks.filter(
    (task) => !task.planned_start_at && !task.due_at && !['completed', 'done', 'cancelled'].includes(task.status),
  )
  const projectOptions = Array.from(projects.values())

  return (
    <div className="kairo-gantt">
      <div className="gantt-toolbar">
        <div className="gantt-range-controls">
          <button type="button" onClick={() => setAnchor((value) => moveAnchor(value, -Math.max(7, Math.round(scale * .7))))}>←</button>
          <button type="button" onClick={() => setAnchor(new Date())}>Aujourd’hui</button>
          <button type="button" onClick={() => setAnchor((value) => moveAnchor(value, Math.max(7, Math.round(scale * .7))))}>→</button>
        </div>
        <select value={projectFilter} onChange={(event) => setProjectFilter(event.target.value)}>
          <option value="">Tous les projets</option>
          {projectOptions.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>
        <div className="gantt-scale">
          {([14, 30, 90] as ScaleDays[]).map((value) => (
            <button key={value} type="button" className={scale === value ? 'gantt-scale-active' : ''} onClick={() => setScale(value)}>{value} j</button>
          ))}
        </div>
      </div>

      <div className="gantt-grid">
        <div className="gantt-header-label">
          <strong>Planification</strong>
          <span>{items.length} tâche(s) visible(s)</span>
        </div>
        <div className="gantt-header-timeline">
          {visibleTicks.map((tick) => (
            <span key={tick.key} className={tick.today ? 'gantt-tick-today' : ''} style={{ left: `${tick.leftPct}%` }}>{tick.label}</span>
          ))}
        </div>

        {items.map((item) => {
          const task = taskById.get(item.taskId)
          if (!task) return null
          const duePct = duePosition(item.sourceDue, window)
          return (
            <div className="gantt-row" key={item.taskId}>
              <button type="button" className="gantt-task-label" onClick={() => onExploreEntity({ entity_type: 'task', entity_id: item.taskId })}>
                <strong>{item.title}</strong>
                <small>{projects.get(item.projectId)?.name || 'Projet'} · P{item.priority}{item.sourceDue ? ` · échéance ${dateLabel(item.sourceDue)}` : ''}</small>
              </button>
              <div className="gantt-track">
                {ticks.map((tick) => <i key={tick.key} className={`${tick.weekend ? 'gantt-day-weekend' : ''} ${tick.today ? 'gantt-day-today' : ''}`} style={{ left: `${tick.leftPct}%` }} />)}
                {item.kind === 'interval' ? (
                  <button
                    type="button"
                    className={`gantt-bar gantt-bar-priority-${item.priority}`}
                    style={{ left: `${item.leftPct}%`, width: `${item.widthPct}%` }}
                    title={`${item.title}${item.sourceStart ? ` · ${dateLabel(item.sourceStart)}` : ''}${item.sourceEnd ? ` → ${dateLabel(item.sourceEnd)}` : ''}`}
                    onClick={() => onExploreEntity({ entity_type: 'task', entity_id: item.taskId })}
                  >
                    <span>{scale <= 30 ? item.title : ''}</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    className={`gantt-milestone gantt-bar-priority-${item.priority}`}
                    style={{ left: `${item.leftPct}%` }}
                    title={`Échéance · ${item.title}`}
                    onClick={() => onExploreEntity({ entity_type: 'task', entity_id: item.taskId })}
                  />
                )}
                {duePct !== null && item.kind === 'interval' && <span className="gantt-due-marker" style={{ left: `${duePct}%` }} title={`Échéance ${dateLabel(item.sourceDue) || ''}`} />}
              </div>
            </div>
          )
        })}

        {items.length === 0 && (
          <div className="gantt-empty">
            <strong>Aucun créneau dans cette fenêtre.</strong>
            <span>Planifiez un début/une fin ou une échéance depuis Aujourd’hui/Toutes.</span>
          </div>
        )}
      </div>

      {unscheduled.length > 0 && (
        <section className="gantt-unscheduled">
          <header><strong>Non planifiées</strong><span>{unscheduled.length}</span></header>
          <div>
            {unscheduled.slice(0, 12).map((task) => (
              <button key={task.id} type="button" onClick={() => onExploreEntity({ entity_type: 'task', entity_id: task.id })}>
                <strong>{task.title}</strong><small>{projects.get(task.project_id)?.name || 'Projet'}</small>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
