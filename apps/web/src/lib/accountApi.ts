import { apiJson } from './api'

export type AccountRetentionBoundary = {
  key: string
  state: 'canonical' | 'derived' | 'shared_retention' | 'external'
  detail: string
}

export type AccountDataInventory = {
  generated_at: string
  canonical_counts: Record<string, number>
  canonical_rows_total: number
  object_storage: {
    tracked_objects: number
    tracked_bytes: number
    boundary: 'seaweedfs_assets'
  }
  derived_projections: {
    memory_projection_records: number
    projectors: string[]
    canonical: false
    purge_adapter_available: boolean
    latest_canonical_message_at?: string | null
    latest_completed_purge_cutoff_at?: string | null
    purge_current: boolean
  }
  evidence: {
    subject_owned_audit_records: number
    shared_audit_actor_references: number
    subject_owned_outbox_events: number
    unpublished_subject_outbox_events: number
    data_subject_addressable: boolean
    retention_action_available: boolean
  }
  boundaries: AccountRetentionBoundary[]
}

export type AccountExportManifest = {
  schema_version: 'kairo.account-export-manifest.v1'
  generated_at: string
  status: 'manifest_only'
  inventory: AccountDataInventory
  includes: string[]
  excludes: string[]
  bundle_export_available: boolean
}

export type AccountErasureBlocker = {
  code: string
  scope: 'canonical' | 'complete'
  count?: number | null
  resolvable_by_user: boolean
  detail: string
}

export type AccountErasurePreflight = {
  generated_at: string
  canonical_delete_ready: boolean
  complete_erasure_ready: boolean
  blockers: AccountErasureBlocker[]
  inventory: AccountDataInventory
  destructive_endpoint_available: boolean
}

export type DerivedMemoryPurgeRun = {
  task_id: string
  workflow_execution_id?: string | null
  workflow_status?: string | null
  cutoff_message_created_at?: string | null
  already_running: boolean
}

export type AccountLifecycleTask = {
  id: string
  status: string
  completed_at?: string | null
}

export type EvidenceRetentionBlocker = {
  code: string
  count?: number | null
  detail: string
}

export type EvidenceRetentionPlan = {
  generated_at: string
  mode: 'minimize_audit_delete_outbox'
  subject_owned_audit_records: number
  shared_audit_actor_references: number
  subject_owned_outbox_events: number
  unpublished_subject_outbox_events: number
  mapped_published_outbox_events: number
  unmapped_published_outbox_events: number
  partial_receipt_outbox_events: number
  historical_unmapped_safe_after?: string | null
  batch_limit: number
  request_ready: boolean
  blockers: EvidenceRetentionBlocker[]
}

export type EvidenceRetentionResult = {
  status: 'partial' | 'complete'
  outbox_rows_removed: number
  jetstream_messages_deleted: number
  jetstream_messages_already_absent: number
  historical_transport_expiry_accepted: number
  audit_rows_minimized: number
  shared_actor_references_redacted: number
  remaining_subject_outbox_events: number
  remaining_subject_audit_records: number
  remaining_shared_actor_references: number
}

export function fetchAccountDataInventory(): Promise<AccountDataInventory> {
  return apiJson('/v1/account/data-inventory')
}

export function fetchAccountExportManifest(): Promise<AccountExportManifest> {
  return apiJson('/v1/account/export/manifest')
}

export function fetchAccountErasurePreflight(): Promise<AccountErasurePreflight> {
  return apiJson('/v1/account/erasure/preflight')
}

export function fetchEvidenceRetentionPlan(): Promise<EvidenceRetentionPlan> {
  return apiJson('/v1/account/evidence/retention')
}

export function applyEvidenceRetention(): Promise<EvidenceRetentionResult> {
  return apiJson('/v1/account/evidence/retention/apply', {
    method: 'POST',
    body: JSON.stringify({ confirmation: 'MINIMIZE_ACCOUNT_EVIDENCE' }),
  })
}

export function purgeDerivedMemory(): Promise<DerivedMemoryPurgeRun> {
  return apiJson('/v1/account/derived-memory/purge', { method: 'POST' })
}

export function fetchAccountLifecycleTask(taskId: string): Promise<AccountLifecycleTask> {
  return apiJson(`/v1/tasks/${encodeURIComponent(taskId)}`)
}
