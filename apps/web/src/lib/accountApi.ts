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

export function fetchAccountDataInventory(): Promise<AccountDataInventory> {
  return apiJson('/v1/account/data-inventory')
}

export function fetchAccountExportManifest(): Promise<AccountExportManifest> {
  return apiJson('/v1/account/export/manifest')
}

export function fetchAccountErasurePreflight(): Promise<AccountErasurePreflight> {
  return apiJson('/v1/account/erasure/preflight')
}

export function purgeDerivedMemory(): Promise<DerivedMemoryPurgeRun> {
  return apiJson('/v1/account/derived-memory/purge', { method: 'POST' })
}
