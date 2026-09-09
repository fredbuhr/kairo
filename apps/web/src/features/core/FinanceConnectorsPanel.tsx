import { FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { ProjectRecord } from '../../lib/api'
import { fetchSecretReferences } from '../../lib/automationApi'
import {
  createFinanceConnector,
  fetchFinanceConnectors,
  syncFinanceConnector,
  updateFinanceConnector,
  type FinanceConnectorRecord,
} from '../../lib/financeApi'

function shortDateTime(value?: string | null) {
  if (!value) return 'Jamais'
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

function ConnectorCard({ connector }: { connector: FinanceConnectorRecord }) {
  const client = useQueryClient()
  const policy = useMutation({
    mutationFn: () => updateFinanceConnector(connector.id, { enabled: !connector.enabled }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['finance-connectors'] })
    },
  })
  const sync = useMutation({
    mutationFn: () => syncFinanceConnector(connector.id),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['finance-connectors'] }),
        client.invalidateQueries({ queryKey: ['finance-portfolio'] }),
        client.invalidateQueries({ queryKey: ['agent-executions'] }),
      ])
    },
  })
  const actionError = policy.error || sync.error

  return (
    <article className={`finance-connector-card ${connector.enabled ? 'finance-connector-enabled' : ''}`}>
      <header>
        <div><strong>{connector.display_name}</strong><span>Rotki · {connector.key}</span></div>
        <i className={connector.enabled ? 'finance-connector-live' : ''} />
      </header>
      <dl>
        <div><dt>Source</dt><dd>{connector.source_key}</dd></div>
        <div><dt>Dernière synchro</dt><dd>{shortDateTime(connector.last_sync_at)}</dd></div>
        <div><dt>Refresh distant</dt><dd>{connector.refresh_remote ? 'Oui' : 'Cache seulement'}</dd></div>
      </dl>
      {connector.last_error && <p className="finance-connector-error">{connector.last_error}</p>}
      <div className="finance-connector-actions">
        <button type="button" disabled={policy.isPending} onClick={() => policy.mutate()}>{policy.isPending ? '…' : connector.enabled ? 'Désactiver' : 'Activer'}</button>
        <button type="button" disabled={!connector.enabled || sync.isPending} onClick={() => sync.mutate()}>{sync.isPending ? 'Synchro…' : 'Synchroniser'}</button>
      </div>
      {actionError && <small className="workspace-error">{actionError instanceof Error ? actionError.message : 'Action impossible.'}</small>}
    </article>
  )
}

export function FinanceConnectorsPanel({ projects }: { projects: ProjectRecord[] }) {
  const client = useQueryClient()
  const connectorsQuery = useQuery({
    queryKey: ['finance-connectors'],
    queryFn: fetchFinanceConnectors,
    staleTime: 10_000,
  })
  const secretsQuery = useQuery({
    queryKey: ['secret-references'],
    queryFn: fetchSecretReferences,
    staleTime: 30_000,
  })
  const [creating, setCreating] = useState(false)
  const [projectId, setProjectId] = useState('')
  const [displayName, setDisplayName] = useState('Mon portefeuille Rotki')
  const [key, setKey] = useState('rotki.main')
  const [secretReferenceId, setSecretReferenceId] = useState('')
  const [usernameKey, setUsernameKey] = useState('username')
  const [passwordKey, setPasswordKey] = useState('password')
  const [refreshRemote, setRefreshRemote] = useState(true)

  const mutation = useMutation({
    mutationFn: () => createFinanceConnector({
      project_id: projectId,
      key: key.trim(),
      display_name: displayName.trim(),
      secret_reference_id: secretReferenceId,
      username_secret_key: usernameKey.trim(),
      password_secret_key: passwordKey.trim(),
      refresh_remote: refreshRemote,
    }),
    onSuccess: async () => {
      setCreating(false)
      await client.invalidateQueries({ queryKey: ['finance-connectors'] })
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!projectId || !displayName.trim() || !key.trim() || !secretReferenceId || mutation.isPending) return
    mutation.mutate()
  }

  const connectors = connectorsQuery.data || []
  const secrets = secretsQuery.data || []
  const error = connectorsQuery.error || secretsQuery.error

  return (
    <section className="finance-connectors-panel">
      <header>
        <div><span className="kairo-kicker">CONNECTEURS</span><strong>Sources Finance</strong></div>
        <button type="button" onClick={() => setCreating((value) => !value)}>{creating ? 'Fermer' : '+ Rotki'}</button>
      </header>

      {error && <small className="workspace-error">{error instanceof Error ? error.message : 'Impossible de lire les connecteurs.'}</small>}
      {connectors.length === 0 && !creating && <div className="finance-connectors-empty"><strong>Aucun connecteur.</strong><span>Ajoutez Rotki sans exposer ses identifiants au navigateur.</span></div>}
      {connectors.map((connector) => <ConnectorCard key={connector.id} connector={connector} />)}

      {creating && (
        <form className="finance-connector-form" onSubmit={submit}>
          <p>Les identifiants Rotki restent dans OpenBao. KAIRO ne stocke ici qu’une référence vers le secret.</p>
          <label><span>Projet</span><select value={projectId} onChange={(event) => setProjectId(event.target.value)}><option value="">Choisir…</option>{projects.filter((project) => project.status !== 'archived').map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
          <label><span>Nom</span><input value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label>
          <label><span>Clé KAIRO</span><input value={key} onChange={(event) => setKey(event.target.value)} /></label>
          <label><span>SecretReference</span><select value={secretReferenceId} onChange={(event) => setSecretReferenceId(event.target.value)}><option value="">Choisir…</option>{secrets.map((secret) => <option key={secret.id} value={secret.id}>{secret.name} · {secret.provider_path}</option>)}</select></label>
          <div className="finance-connector-secret-keys">
            <label><span>Champ utilisateur</span><input value={usernameKey} onChange={(event) => setUsernameKey(event.target.value)} /></label>
            <label><span>Champ mot de passe</span><input value={passwordKey} onChange={(event) => setPasswordKey(event.target.value)} /></label>
          </div>
          <label className="finance-connector-check"><input type="checkbox" checked={refreshRemote} onChange={(event) => setRefreshRemote(event.target.checked)} /><span>Demander à Rotki un refresh avant lecture</span></label>
          <button type="submit" disabled={!projectId || !displayName.trim() || !key.trim() || !secretReferenceId || mutation.isPending}>{mutation.isPending ? 'Création…' : 'Créer désactivé'}</button>
          {mutation.isError && <small className="workspace-error">{mutation.error instanceof Error ? mutation.error.message : 'Création impossible.'}</small>}
        </form>
      )}
    </section>
  )
}
