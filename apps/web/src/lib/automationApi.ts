import { apiJson } from './api'

export type SecretReferenceRecord = {
  id: string
  name: string
  provider_path: string
  purpose: string
  created_at: string
  updated_at: string
}

export type AutomationRecord = {
  id: string
  project_id: string
  key: string
  name: string
  description?: string | null
  engine: 'activepieces_webhook' | string
  enabled: boolean
  authority_level: number
  webhook_secret_reference_id: string
  webhook_secret_key: string
  timeout_seconds: number
  metadata_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type AutomationRunRecord = {
  id: string
  automation_id: string
  task_id: string
  workflow_execution_id?: string | null
  idempotency_key: string
  correlation_id: string
  status: string
  input_json: Record<string, unknown>
  result_json: Record<string, unknown>
  response_status?: number | null
  outcome_ambiguous: boolean
  last_error?: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

export type AutomationRunCreated = {
  invocation: AutomationRunRecord
  task_id: string
  workflow_execution_id?: string | null
  workflow_status?: string | null
}

export type AutomationCreateInput = {
  project_id: string
  key: string
  name: string
  description?: string | null
  authority_level?: number
  webhook_secret_reference_id: string
  webhook_secret_key?: string
  timeout_seconds?: number
  metadata?: Record<string, unknown>
}

export function fetchAutomations(): Promise<AutomationRecord[]> {
  return apiJson('/v1/automations')
}

export function createAutomation(input: AutomationCreateInput): Promise<AutomationRecord> {
  return apiJson('/v1/automations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...input,
      engine: 'activepieces_webhook',
      webhook_secret_key: input.webhook_secret_key || 'path',
      timeout_seconds: input.timeout_seconds ?? 60,
      metadata: input.metadata || {},
    }),
  })
}

export function updateAutomation(
  automationId: string,
  input: Partial<Pick<AutomationRecord, 'name' | 'description' | 'enabled' | 'authority_level' | 'webhook_secret_reference_id' | 'webhook_secret_key' | 'timeout_seconds'>>,
): Promise<AutomationRecord> {
  return apiJson(`/v1/automations/${encodeURIComponent(automationId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function invokeAutomation(
  automationId: string,
  input: Record<string, unknown>,
  idempotencyKey?: string,
): Promise<AutomationRunCreated> {
  return apiJson(`/v1/automations/${encodeURIComponent(automationId)}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input, idempotency_key: idempotencyKey || null }),
  })
}

export function fetchAutomationRuns(automationId?: string): Promise<AutomationRunRecord[]> {
  const query = automationId ? `?automation_id=${encodeURIComponent(automationId)}` : ''
  return apiJson(`/v1/automation-runs${query}`)
}

export function fetchSecretReferences(): Promise<SecretReferenceRecord[]> {
  return apiJson('/v1/secret-references')
}
