import { apiJson } from './api'

export type FinanceSourceRecord = {
  id: string
  key: string
  provider: string
  source_type: string
  external_account_ref: string
  display_name: string
  status: string
  metadata_json: Record<string, unknown>
  last_sync_at?: string | null
  last_error?: string | null
  created_at: string
  updated_at: string
}

export type FinanceAccountRecord = {
  id: string
  source_id: string
  external_id: string
  label: string
  account_type: string
  network?: string | null
  public_address?: string | null
  metadata_json: Record<string, unknown>
  observed_at: string
  created_at: string
  updated_at: string
}

export type FinancePositionRecord = {
  id: string
  source_id: string
  source_key: string
  source_provider: string
  source_display_name: string
  account_id: string
  account_external_id: string
  account_label: string
  account_type: string
  network?: string | null
  public_address?: string | null
  asset_key: string
  symbol: string
  name?: string | null
  asset_type: string
  quantity: string | number
  unit_price_usd?: string | number | null
  value_usd: string | number
  cost_basis_usd?: string | number | null
  unrealized_pnl_usd?: string | number | null
  metadata: Record<string, unknown>
  observed_at: string
}

export type FinancePortfolioRecord = {
  generated_at: string
  currency: 'USD'
  total_value_usd: string | number
  total_cost_basis_usd?: string | number | null
  total_unrealized_pnl_usd?: string | number | null
  sources: FinanceSourceRecord[]
  accounts: FinanceAccountRecord[]
  positions: FinancePositionRecord[]
}

export type FinanceTransactionProposalRecord = {
  id: string
  project_id?: string | null
  from_account_id?: string | null
  kind: string
  network: string
  asset_key: string
  symbol: string
  amount: string | number
  destination: string
  memo?: string | null
  estimated_fee_asset?: string | null
  estimated_fee_amount?: string | number | null
  simulation_json: Record<string, unknown>
  status: string
  created_by: string
  created_at: string
  updated_at: string
  signing_required: true
  signing_boundary: 'external_isolated_signer'
}

export type FinanceTransactionProposalCreate = {
  project_id?: string | null
  from_account_id: string
  network: string
  asset_key: string
  symbol: string
  amount: string | number
  destination: string
  memo?: string | null
  estimated_fee_asset?: string | null
  estimated_fee_amount?: string | number | null
  simulation?: Record<string, unknown>
}

export type FinanceConnectorRecord = {
  id: string
  project_id: string
  key: string
  provider: 'rotki'
  display_name: string
  enabled: boolean
  secret_reference_id: string
  username_secret_key: string
  password_secret_key: string
  source_key: string
  refresh_remote: boolean
  metadata_json: Record<string, unknown>
  last_sync_at?: string | null
  last_error?: string | null
  created_at: string
  updated_at: string
}

export type FinanceConnectorCreate = {
  project_id: string
  key: string
  display_name: string
  secret_reference_id: string
  username_secret_key?: string
  password_secret_key?: string
  source_key?: string | null
  refresh_remote?: boolean
  metadata?: Record<string, unknown>
}

export type FinanceConnectorSyncRecord = {
  connector: FinanceConnectorRecord
  task_id: string
  workflow_execution_id?: string | null
  workflow_status?: string | null
}

export function fetchFinancePortfolio(sourceId?: string): Promise<FinancePortfolioRecord> {
  const query = sourceId ? `?source_id=${encodeURIComponent(sourceId)}` : ''
  return apiJson(`/v1/finance/portfolio${query}`)
}

export function fetchFinanceTransactionProposals(): Promise<FinanceTransactionProposalRecord[]> {
  return apiJson('/v1/finance/transaction-proposals')
}

export function createFinanceTransactionProposal(
  input: FinanceTransactionProposalCreate,
): Promise<FinanceTransactionProposalRecord> {
  return apiJson('/v1/finance/transaction-proposals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...input,
      kind: 'crypto_transfer',
      simulation: input.simulation || {},
    }),
  })
}

export function fetchFinanceConnectors(): Promise<FinanceConnectorRecord[]> {
  return apiJson('/v1/finance/connectors')
}

export function createFinanceConnector(input: FinanceConnectorCreate): Promise<FinanceConnectorRecord> {
  return apiJson('/v1/finance/connectors', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...input,
      provider: 'rotki',
      username_secret_key: input.username_secret_key || 'username',
      password_secret_key: input.password_secret_key || 'password',
      source_key: input.source_key || null,
      refresh_remote: input.refresh_remote ?? true,
      metadata: input.metadata || {},
    }),
  })
}

export function updateFinanceConnector(
  connectorId: string,
  input: Partial<Pick<FinanceConnectorRecord, 'display_name' | 'enabled' | 'secret_reference_id' | 'username_secret_key' | 'password_secret_key' | 'refresh_remote'>> & { metadata?: Record<string, unknown> },
): Promise<FinanceConnectorRecord> {
  return apiJson(`/v1/finance/connectors/${encodeURIComponent(connectorId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function syncFinanceConnector(connectorId: string): Promise<FinanceConnectorSyncRecord> {
  return apiJson(`/v1/finance/connectors/${encodeURIComponent(connectorId)}/sync`, {
    method: 'POST',
  })
}
