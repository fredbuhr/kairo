import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  applyEvidenceRetention,
  cancelAccountWriteFreeze,
  fetchAccountErasurePreflight,
  fetchAccountExportManifest,
  fetchAccountLifecycleTask,
  fetchAccountWriteFreeze,
  fetchEvidenceRetentionPlan,
  freezeAccountWrites,
  purgeDerivedMemory,
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

function evidenceCount(inventory: AccountDataInventory) {
  return inventory.evidence.subject_owned_audit_records
    + inventory.evidence.shared_audit_actor_references
    + inventory.evidence.subject_owned_outbox_events
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

function shortDateTime(value?: string | null) {
  if (!value) return '—'
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))
  } catch {
    return value
  }
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
  const client = useQueryClient()
  const [purgePolling, setPurgePolling] = useState(false)
  const preflightQuery = useQuery({
    queryKey: ['account-erasure-preflight'],
    queryFn: fetchAccountErasurePreflight,
    staleTime: 10_000,
  })
  const freezeQuery = useQuery({
    queryKey: ['account-write-freeze'],
    queryFn: fetchAccountWriteFreeze,
    staleTime: 3000,
    retry: false,
  })
  const evidencePlanQuery = useQuery({
    queryKey: ['account-evidence-retention'],
    queryFn: fetchEvidenceRetentionPlan,
    staleTime: 5000,
    retry: false,
  })
  const manifestMutation = useMutation({
    mutationFn: fetchAccountExportManifest,
    onSuccess: (manifest) => downloadJson('kairo-account-export-manifest.json', manifest),
  })
  const freezeMutation = useMutation({
    mutationFn: () => freezeAccountWrites(),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['account-write-freeze'] }),
        client.invalidateQueries({ queryKey: ['account-erasure-preflight'] }),
        client.invalidateQueries({ queryKey: ['account-evidence-retention'] }),
      ])
    },
  })
  const unfreezeMutation = useMutation({
    mutationFn: cancelAccountWriteFreeze,
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['account-write-freeze'] }),
        client.invalidateQueries({ queryKey: ['account-erasure-preflight'] }),
        client.invalidateQueries({ queryKey: ['account-evidence-retention'] }),
      ])
    },
  })
  const purgeMutation = useMutation({
    mutationFn: purgeDerivedMemory,
    onSuccess: async () => {
      setPurgePolling(true)
      await Promise.all([
        client.invalidateQueries({ queryKey: ['account-erasure-preflight'] }),
        client.invalidateQueries({ queryKey: ['account-evidence-retention'] }),
        client.invalidateQueries({ queryKey: ['agent-executions'] }),
      ])
    },
  })
  const evidenceMutation = useMutation({
    mutationFn: applyEvidenceRetention,
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['account-erasure-preflight'] }),
        client.invalidateQueries({ queryKey: ['account-evidence-retention'] }),
      ])
    },
  })
  const purgeTaskId = purgeMutation.data?.task_id || ''
  const purgeTaskQuery = useQuery({
    queryKey: ['account-derived-memory-purge-task', purgeTaskId],
    queryFn: () => fetchAccountLifecycleTask(purgeTaskId),
    enabled: Boolean(purgeTaskId),
    refetchInterval: purgePolling ? 1500 : false,
    retry: false,
  })

  const preflight = preflightQuery.data
  const inventory = preflight?.inventory
  const freeze = freezeQuery.data
  const derived = inventory?.derived_projections
  const evidencePlan = evidencePlanQuery.data
  const purgeTaskStatus = purgeTaskQuery.data?.status
  const error = preflightQuery.error
    || freezeQuery.error
    || evidencePlanQuery.error
    || manifestMutation.error
    || freezeMutation.error
    || unfreezeMutation.error
    || purgeMutation.error
    || evidenceMutation.error
    || purgeTaskQuery.error

  useEffect(() => {
    if (!purgePolling || !purgeTaskStatus) return
    if (purgeTaskStatus === 'completed' || purgeTaskStatus === 'done') {
      setPurgePolling(false)
      void Promise.all([
        client.invalidateQueries({ queryKey: ['account-erasure-preflight'] }),
        client.invalidateQueries({ queryKey: ['account-evidence-retention'] }),
        client.invalidateQueries({ queryKey: ['agent-executions'] }),
      ])
    } else if (['failed', 'cancelled', 'archived'].includes(purgeTaskStatus)) {
      setPurgePolling(false)
      void client.invalidateQueries({ queryKey: ['account-erasure-preflight'] })
    }
  }, [client, purgePolling, purgeTaskStatus])

  function requestFreeze() {
    if (freeze?.frozen || freezeMutation.isPending) return
    const confirmed = window.confirm(
      'Geler les écritures de ce compte ?\n\nLes lectures resteront disponibles, mais les créations et modifications ordinaires seront refusées avec HTTP 423. Le gel est réversible tant que la suppression complète n’existe pas.',
    )
    if (confirmed) freezeMutation.mutate()
  }

  function requestUnfreeze() {
    if (!freeze?.frozen || unfreezeMutation.isPending) return
    const confirmed = window.confirm(
      'Réactiver les écritures ?\n\nCette action recrée de la traçabilité et invalide toute préparation de suppression précédente.',
    )
    if (confirmed) unfreezeMutation.mutate()
  }

  function requestPurge() {
    if (!derived || purgeMutation.isPending || derived.purge_current) return
    const confirmed = window.confirm(
      'Purger la mémoire dérivée Mem0 / Graphiti ?\n\nLes conversations canoniques resteront intactes. Seules les projections reconstruisibles seront supprimées.',
    )
    if (confirmed) purgeMutation.mutate()
  }

  function requestEvidenceRetention() {
    if (!evidencePlan?.request_ready || evidenceMutation.isPending) return
    const confirmed = window.confirm(
      'Appliquer la rétention Audit / Outbox ?\n\nCette opération est irréversible : KAIRO retire les copies JetStream identifiées, supprime les lignes Outbox réconciliées et minimise les détails d’audit personnels. Les données canoniques ne sont pas supprimées.',
    )
    if (confirmed) evidenceMutation.mutate()
  }

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
              <strong>{derived?.memory_projection_records || 0}</strong>
            </div>
            <div>
              <span>Traçabilité</span>
              <strong>{evidenceCount(inventory)} · {inventory.evidence.unpublished_subject_outbox_events} en transit</strong>
            </div>
          </div>

          {freeze && (
            <div className={`account-write-freeze ${freeze.frozen ? 'account-write-freeze-active' : ''}`}>
              <div>
                <span className="kairo-kicker">GEL DES ÉCRITURES</span>
                <strong>{freeze.frozen ? 'Écritures utilisateur gelées' : 'Compte actif'}</strong>
                <small>
                  {freeze.frozen
                    ? `Depuis ${shortDateTime(freeze.frozen_at)} · opération ${freeze.operation_id?.slice(0, 8) || '—'}…`
                    : 'Les mutations ordinaires du Cockpit sont autorisées.'}
                </small>
              </div>
              <button
                type="button"
                disabled={freezeMutation.isPending || unfreezeMutation.isPending}
                onClick={freeze.frozen ? requestUnfreeze : requestFreeze}
              >
                {freezeMutation.isPending
                  ? 'Gel…'
                  : unfreezeMutation.isPending
                    ? 'Réactivation…'
                    : freeze.frozen
                      ? 'Réactiver les écritures'
                      : 'Geler les écritures'}
              </button>
              <p>
                Ce gel local bloque immédiatement les nouveaux POST/PUT/PATCH/DELETE issus du bearer utilisateur, y compris si Keycloak avait déjà émis ce token. Les lectures et les primitives bornées de préparation à l’effacement restent disponibles. Il ne supprime aucune donnée et ne désactive pas encore l’identité Keycloak.
              </p>
            </div>
          )}

          <div className="account-evidence-note">
            <span className="kairo-kicker">AUDIT & ÉVÉNEMENTS</span>
            <p>
              {inventory.evidence.data_subject_addressable
                ? 'Les preuves de votre monde KAIRO sont adressables par propriétaire. La rétention retire d’abord les copies transport, puis minimise les détails personnels sans supprimer les données canoniques.'
                : 'Certaines preuves ne sont pas encore adressables par propriétaire.'}
            </p>
            <small>
              Audit personnel : {inventory.evidence.subject_owned_audit_records} · références acteur dans l’audit partagé : {inventory.evidence.shared_audit_actor_references} · Outbox : {inventory.evidence.subject_owned_outbox_events}
            </small>
          </div>

          {evidencePlan && evidenceCount(inventory) > 0 && (
            <div className={`account-evidence-retention ${evidencePlan.request_ready ? 'account-evidence-ready' : ''}`}>
              <div>
                <span className="kairo-kicker">RÉTENTION AUDIT / OUTBOX</span>
                <strong>{evidencePlan.request_ready ? 'Réconciliation disponible' : 'Réconciliation bloquée'}</strong>
                <small>
                  JetStream identifié : {evidencePlan.mapped_published_outbox_events} · historique sans reçu : {evidencePlan.unmapped_published_outbox_events} · en transit : {evidencePlan.unpublished_subject_outbox_events}
                </small>
              </div>
              <button
                type="button"
                disabled={!evidencePlan.request_ready || evidenceMutation.isPending}
                onClick={requestEvidenceRetention}
              >
                {evidenceMutation.isPending ? 'Réconciliation…' : 'Appliquer la rétention'}
              </button>
              <p>
                Les événements avec reçu stream/séquence sont retirés de JetStream avant leur Outbox PostgreSQL. Les anciens événements sans reçu attendent leur expiration max-age avant d’être considérés absents.
              </p>
              {evidencePlan.historical_unmapped_safe_after && !evidencePlan.request_ready && (
                <small>Fin de la fenêtre historique : {shortDateTime(evidencePlan.historical_unmapped_safe_after)}</small>
              )}
              {evidencePlan.blockers.length > 0 && (
                <small>{evidencePlan.blockers.map((blocker) => blocker.detail).join(' · ')}</small>
              )}
              {evidenceMutation.data && (
                <small>
                  {evidenceMutation.data.status === 'complete' ? 'Rétention appliquée.' : 'Lot traité, une nouvelle passe est nécessaire.'}
                  {' '}Outbox retiré : {evidenceMutation.data.outbox_rows_removed} · Audit minimisé : {evidenceMutation.data.audit_rows_minimized}
                </small>
              )}
            </div>
          )}

          {derived && (
            <div className={`derived-memory-control ${derived.purge_current ? 'derived-memory-current' : ''}`}>
              <div>
                <span className="kairo-kicker">MÉMOIRE DÉRIVÉE</span>
                <strong>{derived.purge_current ? 'Projection purgée au dernier état canonique' : 'Projection à purger'}</strong>
                <small>
                  Dernier message : {shortDateTime(derived.latest_canonical_message_at)} · dernier cutoff purgé : {shortDateTime(derived.latest_completed_purge_cutoff_at)}
                </small>
              </div>
              <button
                type="button"
                disabled={!derived.purge_adapter_available || derived.purge_current || purgeMutation.isPending || purgePolling}
                onClick={requestPurge}
              >
                {purgeMutation.isPending || purgePolling ? 'Purge en cours…' : derived.purge_current ? 'À jour' : 'Purger Mem0 / Graphiti'}
              </button>
              <p>
                Cette opération supprime uniquement les projections reconstruisibles. Les messages et conversations canoniques restent dans KAIRO.
              </p>
              {purgeMutation.data && (
                <small>
                  Task {purgeMutation.data.task_id.slice(0, 8)}… · {purgeTaskStatus || (purgeMutation.data.already_running ? 'exécution déjà active' : 'exécution demandée')}
                </small>
              )}
            </div>
          )}

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
