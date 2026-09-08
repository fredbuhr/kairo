export type AuthorityLevel = 'A0' | 'A1' | 'A2' | 'A3' | 'A4' | 'A5'

export type EpistemicStatus = 'fact' | 'hypothesis' | 'deduction' | 'opinion' | 'unknown'

export interface EntityRef {
  id: string
  type: string
}

export interface PolicyContext {
  actorId: string
  deviceId?: string
  projectId?: string
  authorityCeiling: AuthorityLevel
  correlationId: string
}

export interface DomainEvent<T = unknown> {
  id: string
  type: string
  occurredAt: string
  actorId: string
  correlationId: string
  entity: EntityRef
  payload: T
}
