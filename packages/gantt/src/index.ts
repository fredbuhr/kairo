export interface ScheduledTask {
  taskId: string
  start: string
  end: string
  progress?: number
  dependencies: string[]
}

export interface PlanVersion {
  id: string
  status: 'draft' | 'proposed' | 'accepted' | 'superseded'
  tasks: ScheduledTask[]
}

export interface CanonicalPlanningTask {
  taskId: string
  title: string
  projectId: string
  plannedStart?: string | null
  plannedEnd?: string | null
  dueAt?: string | null
  priority: number
  status: string
}

export interface GanttWindow {
  startMs: number
  endMs: number
  days: number
}

export interface GanttTick {
  key: string
  label: string
  leftPct: number
  weekend: boolean
  today: boolean
}

export interface GanttVisualItem {
  taskId: string
  title: string
  projectId: string
  priority: number
  status: string
  kind: 'interval' | 'milestone'
  leftPct: number
  widthPct: number
  startsBeforeWindow: boolean
  endsAfterWindow: boolean
  sourceStart?: string | null
  sourceEnd?: string | null
  sourceDue?: string | null
}

const DAY_MS = 86_400_000

function safeDate(value?: string | null): number | null {
  if (!value) return null
  const time = new Date(value).getTime()
  return Number.isFinite(time) ? time : null
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

export function buildGanttWindow(anchor: Date, days: number, leadDays?: number): GanttWindow {
  const normalizedDays = Math.max(7, Math.min(180, Math.round(days)))
  const lead = leadDays ?? Math.min(7, Math.max(2, Math.round(normalizedDays * 0.2)))
  const localMidnight = new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate())
  const startMs = localMidnight.getTime() - lead * DAY_MS
  return {
    startMs,
    endMs: startMs + normalizedDays * DAY_MS,
    days: normalizedDays,
  }
}

export function buildGanttTicks(window: GanttWindow, locale = 'fr-FR'): GanttTick[] {
  const formatter = new Intl.DateTimeFormat(locale, { weekday: 'short', day: '2-digit', month: 'short' })
  const now = new Date()
  const todayKey = `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}`
  const ticks: GanttTick[] = []
  for (let index = 0; index <= window.days; index += 1) {
    const date = new Date(window.startMs + index * DAY_MS)
    const dayKey = `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
    ticks.push({
      key: `${date.toISOString()}:${index}`,
      label: formatter.format(date),
      leftPct: index / window.days * 100,
      weekend: date.getDay() === 0 || date.getDay() === 6,
      today: dayKey === todayKey,
    })
  }
  return ticks
}

export function projectGanttItems(
  tasks: CanonicalPlanningTask[],
  window: GanttWindow,
): GanttVisualItem[] {
  const duration = Math.max(1, window.endMs - window.startMs)
  const items: GanttVisualItem[] = []

  for (const task of tasks) {
    const plannedStart = safeDate(task.plannedStart)
    const plannedEnd = safeDate(task.plannedEnd)
    const dueAt = safeDate(task.dueAt)

    if (plannedStart !== null) {
      const explicitEnd = plannedEnd ?? plannedStart
      if (explicitEnd < window.startMs || plannedStart > window.endMs) continue
      const visibleStart = clamp(plannedStart, window.startMs, window.endMs)
      const visibleEnd = clamp(Math.max(explicitEnd, plannedStart), window.startMs, window.endMs)
      const leftPct = (visibleStart - window.startMs) / duration * 100
      const rawWidth = (visibleEnd - visibleStart) / duration * 100
      items.push({
        taskId: task.taskId,
        title: task.title,
        projectId: task.projectId,
        priority: task.priority,
        status: task.status,
        kind: 'interval',
        leftPct,
        // An instantaneous explicit start remains a visible marker-width bar; this is rendering only.
        widthPct: Math.max(0.55, rawWidth),
        startsBeforeWindow: plannedStart < window.startMs,
        endsAfterWindow: explicitEnd > window.endMs,
        sourceStart: task.plannedStart,
        sourceEnd: task.plannedEnd,
        sourceDue: task.dueAt,
      })
      continue
    }

    if (dueAt !== null && dueAt >= window.startMs && dueAt <= window.endMs) {
      items.push({
        taskId: task.taskId,
        title: task.title,
        projectId: task.projectId,
        priority: task.priority,
        status: task.status,
        kind: 'milestone',
        leftPct: (dueAt - window.startMs) / duration * 100,
        widthPct: 0,
        startsBeforeWindow: false,
        endsAfterWindow: false,
        sourceStart: task.plannedStart,
        sourceEnd: task.plannedEnd,
        sourceDue: task.dueAt,
      })
    }
  }

  return items.sort((a, b) => a.leftPct - b.leftPct || b.priority - a.priority || a.title.localeCompare(b.title))
}
