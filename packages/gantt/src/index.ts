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
