import { useMutation, useQuery } from '@tanstack/react-query'

import {
  fetchAccountErasurePreflight,
  fetchAccountExportManifest,
  type AccountDataInventory,
} from '../../lib/accountApi'

const COUNT_GROUPS: Array<{ label: string; keys: string[] }> = [
  { label: 'Travail', keys: ['projects', 'tasks', 'workflow_executions', 'artifacts', 'approval_requests'] },
  { label: 'Connaissances', keys: ['assets', 'documents', 'document_versions', 'document_chunks', 'relationships'] },
  { label: 'Conversation', keys: ['conversations', 'conversation_messages', 'commands', 'model_usage_records'] },
  { label: 'Connexions', keys: ['secret_references', 'calendar_sources', 'external_calendar_events', 'finance_sources', 'finance_accounts', 'finance_positions', 'finance_transaction_proposals', 'finance_connectors', 'automation_definitions', 'automation_invocations', 'tool_invocations', 'devices'] },
]

function groupCount(inventory: AccountDataInventory, keys: string[]) {
  return keys.reduce((sum, key) => sum + (inventory.canonical_counts[key] || 0), 0)
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} o`
  const units = ['Ko', 'Mo', 'Go', 'To']
  let value = bytes / 1024
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value >= 10 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`
}

function downloadJson(filename: string, value: unknown) {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export function AccountDataLifecycleSettings() {
  const preflightQuery = useQuery({
    queryKey: ['account-erasure-preflight'],
    queryFn: fetchAccountErasurePreflight,
    staleTime: 10_000,
  })
  const manifestMutation = useMutation({
    mutationFn: fetchAccountExportManifest,
    onSuccess: (manifest) => downloadJson('kairo-account-export-manifest.json', manifest),
  })

  const preflight = preflightQuery.data
  const inventory = preflight?.inventory
  const error = preflightQuery.error || manifestMutation.error

  return (
    <section className="account-lifecycle-settings">
      <header>
        <div>
          <span className="kairo-kicker">VOS DONNÉES</span>
          <strong>Inventaire, export & suppression</strong>
        </div>
        {inventory && <b>{inventory.canonical_rows_total} lignes canoniques</b>}
      </header>

      <p>
        KAIRO distingue les données canoniques, les fichiers, les secrets, les projections reconstruisibles et les systèmes externes.
        Une suppression complète n’est jamais assimilée à un simple effacement SQL.
      </p>

      {preflightQuery.isLoading ? (
        <span className="account-lifecycle-muted">Construction de l’inventaire personnel…</span>
      ) : inventory ? (
        <>
          <div className="account-lifecycle-summary">
            {COUNT_GROUPS.map((group) => (
              <div key={group.label}>
                <span>{group.label}</span>
                <strong>{groupCount(inventory, group.keys)}</strong>
              </div>
            ))}
            <div>
              <span>Fichiers</span>
              <strong>{inventory.object_storage.tracked_objects} · {formatBytes(inventory.object_storage.tracked_bytes)}</strong>
            </div>
            <div>
              <span>Projections mémoire</span>
              <strong>{inventory.derived_projections.memory_projection_records}</strong>
            </div>
          </div>

          <div className="account-lifecycle-actions">
            <button
              type="button"
              disabled={manifestMutation.isPending}
              onClick={() => manifestMutation.mutate()}
            >
              {manifestMutation.isPending ? 'Préparation…' : 'Exporter le manifeste JSON'}
            </button>
            <button type="button" disabled title="La suppression destructive reste désactivée tant que toutes les frontières ne sont pas purgeables.">
              Suppression complète non activée
            </button>
          </div>

          <small className="account-lifecycle-export-note">
            L’export actuel est un manifeste d’inventaire versionné, pas encore un bundle complet. Les valeurs OpenBao ne sont jamais relues ni exportées.
          </small>

          {preflight && (
            <div className="account-erasure-preflight">
              <header>
                <div>
                  <span className="kairo-kicker">PRÉ-VÉRIFICATION</span>
                  <strong>Suppression du compte</strong>
                </div>
                <b className={preflight.canonical_delete_ready ? 'account-state-ready' : 'account-state-blocked'}>
                  {preflight.canonical_delete_ready ? 'CANONIQUE PRÊT' : 'TRAVAIL ACTIF'}
                </b>
              </header>
              <p>
                {preflight.complete_erasure_ready
                  ? 'Toutes les frontières déclarées peuvent être purgées.'
                  : 'KAIRO refuse pour l’instant de prétendre à une suppression complète tant que certaines frontières externes ou de rétention restent ouvertes.'}
              </p>
              <div className="account-blocker-list">
                {preflight.blockers.map((blocker) => (
                  <div key={blocker.code}>
                    <i className={blocker.scope === 'canonical' ? 'account-blocker-canonical' : 'account-blocker-complete'} />
                    <span>
                      <strong>{blocker.code.replaceAll('_', ' ')}</strong>
                      <small>{blocker.detail}</small>
                    </span>
                    {blocker.count !== null && blocker.count !== undefined && <b>{blocker.count}</b>}
                  </div>
                ))}
              </div>
            </div>
          )}

          <details className="account-retention-boundaries">
            <summary>Frontières de rétention déclarées</summary>
            {inventory.boundaries.map((boundary) => (
              <div key={boundary.key}>
                <strong>{boundary.key.replaceAll('_', ' ')}</strong>
                <small>{boundary.detail}</small>
              </div>
            ))}
          </details>
        </>
      ) : null}

      {error && (
        <small className="workspace-error">
          {error instanceof Error ? error.message : 'Impossible de lire le cycle de vie des données.'}
        </small>
      )}
    </section>
  )
}
