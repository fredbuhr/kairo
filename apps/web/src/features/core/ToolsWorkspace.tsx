import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createToolServer,
  fetchToolServers,
  fetchTools,
  updateToolPolicy,
  updateToolServerPolicy,
  type ToolDefinitionRecord,
  type ToolServerRecord,
} from '../../lib/toolApi'

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

function money(value: string | number) {
  const parsed = Number(value || 0)
  if (!Number.isFinite(parsed)) return '—'
  if (parsed === 0) return '$0'
  if (parsed < 0.01) return `$${parsed.toFixed(4)}`
  return `$${parsed.toFixed(2)}`
}

function riskLabel(value: ToolDefinitionRecord['risk_class']) {
  return value === 'read' ? 'Lecture' : value === 'write' ? 'Écriture' : 'Destructif'
}

function schemaFields(schema?: Record<string, unknown> | null) {
  if (!schema) return []
  const properties = schema.properties
  if (!properties || typeof properties !== 'object' || Array.isArray(properties)) return []
  return Object.keys(properties as Record<string, unknown>).slice(0, 14)
}

function ServerCard({
  server,
  selected,
  onSelect,
}: {
  server: ToolServerRecord
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button type="button" className={`tools-server-card ${selected ? 'tools-server-card-active' : ''}`} onClick={onSelect}>
      <i className={server.enabled ? 'tools-server-live' : ''} />
      <div>
        <strong>{server.title}</strong>
        <small>{server.namespace} · {server.transport}</small>
      </div>
      <span>{server.enabled ? 'Actif' : 'Coupé'}</span>
    </button>
  )
}

function RegisterServer() {
  const client = useQueryClient()
  const [open, setOpen] = useState(false)
  const [key, setKey] = useState('')
  const [namespace, setNamespace] = useState('')
  const [title, setTitle] = useState('')
  const [endpoint, setEndpoint] = useState('')
  const mutation = useMutation({
    mutationFn: () => createToolServer({
      key: key.trim(),
      namespace: namespace.trim(),
      title: title.trim(),
      endpoint_url: endpoint.trim(),
    }),
    onSuccess: async (server) => {
      setKey('')
      setNamespace('')
      setTitle('')
      setEndpoint('')
      setOpen(false)
      await client.invalidateQueries({ queryKey: ['tool-servers'] })
      return server
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!key.trim() || !namespace.trim() || !title.trim() || !endpoint.trim() || mutation.isPending) return
    mutation.mutate()
  }

  if (!open) {
    return <button type="button" className="tools-register-toggle" onClick={() => setOpen(true)}>+ Enregistrer un serveur</button>
  }

  return (
    <form className="workspace-create tools-register" onSubmit={submit}>
      <div className="workspace-create-heading">
        <div><span className="kairo-kicker">NOUVEAU MCP</span><strong>Serveur désactivé à la création</strong></div>
      </div>
      <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Nom affiché" maxLength={240} />
      <input value={key} onChange={(event) => setKey(event.target.value.toLowerCase())} placeholder="clé-exemple" maxLength={120} />
      <input value={namespace} onChange={(event) => setNamespace(event.target.value.toLowerCase())} placeholder="namespace" maxLength={80} />
      <input value={endpoint} onChange={(event) => setEndpoint(event.target.value)} placeholder="https://…/mcp" maxLength={2048} />
      <div className="tools-register-actions">
        <button type="button" onClick={() => setOpen(false)}>Annuler</button>
        <button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}</button>
      </div>
      {mutation.isError && <small className="workspace-error">{mutation.error instanceof Error ? mutation.error.message : 'Enregistrement impossible.'}</small>}
      <small className="tools-register-note">Aucun outil n’est autorisé automatiquement. Le catalogue est alimenté par la passerelle MCP de confiance.</small>
    </form>
  )
}

function ToolCard({
  tool,
  serverEnabled,
  onInspect,
}: {
  tool: ToolDefinitionRecord
  serverEnabled: boolean
  onInspect: () => void
}) {
  const client = useQueryClient()
  const mutation = useMutation({
    mutationFn: () => updateToolPolicy(tool.key, { enabled: !tool.enabled }),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['tools'] }),
        client.invalidateQueries({ queryKey: ['agent-executions'] }),
      ])
    },
  })
  const canEnable = serverEnabled && tool.available

  return (
    <article className={`tools-tool-card tools-risk-${tool.risk_class} ${tool.enabled ? 'tools-tool-enabled' : ''}`}>
      <button type="button" className="tools-tool-main" onClick={onInspect}>
        <div className="tools-tool-heading">
          <div><span>{riskLabel(tool.risk_class)} · A{tool.authority_level}</span><strong>{tool.title}</strong></div>
          <i className={tool.available ? 'tools-tool-available' : ''} />
        </div>
        <p>{tool.description || 'Aucune description déclarée par le serveur MCP.'}</p>
        <div className="tools-tool-meta">
          <span>{tool.remote_name}</span>
          <span>{tool.retry_policy === 'safe_retry' ? 'retry sûr' : 'aucun retry automatique'}</span>
          <span>{money(tool.estimated_cost_usd)}</span>
        </div>
      </button>
      <button
        type="button"
        className={`tools-policy-toggle ${tool.enabled ? 'tools-policy-toggle-on' : ''}`}
        disabled={mutation.isPending || (!tool.enabled && !canEnable)}
        onClick={() => mutation.mutate()}
        title={!serverEnabled ? 'Activez d’abord le serveur MCP' : !tool.available ? 'Outil absent du dernier catalogue' : undefined}
      >
        {mutation.isPending ? '…' : tool.enabled ? 'Autorisé' : 'Interdit'}
      </button>
      {mutation.isError && <small className="workspace-error">{mutation.error instanceof Error ? mutation.error.message : 'Politique impossible.'}</small>}
    </article>
  )
}

function ToolInspector({ tool }: { tool: ToolDefinitionRecord }) {
  const inputFields = schemaFields(tool.input_schema)
  const outputFields = schemaFields(tool.output_schema)
  return (
    <section className="tools-inspector-card">
      <div className="tools-inspector-heading">
        <div><span className="kairo-kicker">CONTRAT MCP</span><h2>{tool.title}</h2></div>
        <b>{riskLabel(tool.risk_class)}</b>
      </div>
      <p>{tool.description || 'Aucune description.'}</p>
      <dl>
        <div><dt>Clé KAIRO</dt><dd>{tool.key}</dd></div>
        <div><dt>Nom distant</dt><dd>{tool.remote_name}</dd></div>
        <div><dt>Autorité</dt><dd>A{tool.authority_level}</dd></div>
        <div><dt>Retry</dt><dd>{tool.retry_policy}</dd></div>
        <div><dt>Coût estimé</dt><dd>{money(tool.estimated_cost_usd)}</dd></div>
        <div><dt>Dernière vue</dt><dd>{shortDateTime(tool.last_seen_at)}</dd></div>
        <div><dt>Schéma</dt><dd>{tool.schema_hash.slice(0, 12)}…</dd></div>
      </dl>
      <div className="tools-schema-fields">
        <div><strong>Entrées</strong>{inputFields.length === 0 ? <span>aucun champ déclaré</span> : inputFields.map((field) => <span key={field}>{field}</span>)}</div>
        <div><strong>Sorties</strong>{outputFields.length === 0 ? <span>aucun champ déclaré</span> : outputFields.map((field) => <span key={field}>{field}</span>)}</div>
      </div>
      <small>Le schéma distant est revalidé par le Worker avant l’exécution réelle ; cet écran n’accorde jamais plus d’autorité que la politique KAIRO.</small>
    </section>
  )
}

export function ToolsWorkspace() {
  const client = useQueryClient()
  const serversQuery = useQuery({
    queryKey: ['tool-servers'],
    queryFn: fetchToolServers,
    staleTime: 7000,
  })
  const allToolsQuery = useQuery({
    queryKey: ['tools'],
    queryFn: fetchTools,
    staleTime: 5000,
  })
  const servers = serversQuery.data || []
  const allTools = allToolsQuery.data || []
  const [serverKey, setServerKey] = useState('')
  const [selectedToolKey, setSelectedToolKey] = useState('')
  const [riskFilter, setRiskFilter] = useState('all')
  const [availabilityFilter, setAvailabilityFilter] = useState('available')

  useEffect(() => {
    if (servers.length === 0) {
      setServerKey('')
      return
    }
    if (!servers.some((server) => server.key === serverKey)) setServerKey(servers[0].key)
  }, [serverKey, servers])

  const selectedServer = servers.find((server) => server.key === serverKey) || null
  const tools = useMemo(
    () => selectedServer ? allTools.filter((tool) => tool.server_id === selectedServer.id) : [],
    [allTools, selectedServer],
  )

  useEffect(() => {
    if (tools.length === 0) {
      setSelectedToolKey('')
      return
    }
    if (!tools.some((tool) => tool.key === selectedToolKey)) setSelectedToolKey(tools[0].key)
  }, [selectedToolKey, tools])

  const selectedTool = tools.find((tool) => tool.key === selectedToolKey) || null
  const visibleTools = useMemo(() => tools.filter((tool) => {
    if (riskFilter !== 'all' && tool.risk_class !== riskFilter) return false
    if (availabilityFilter === 'available' && !tool.available) return false
    if (availabilityFilter === 'enabled' && !tool.enabled) return false
    return true
  }), [availabilityFilter, riskFilter, tools])

  const serverPolicy = useMutation({
    mutationFn: (enabled: boolean) => updateToolServerPolicy(serverKey, enabled),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['tool-servers'] }),
        client.invalidateQueries({ queryKey: ['tools'] }),
      ])
    },
  })
  const error = serversQuery.error || allToolsQuery.error

  if (serversQuery.isLoading || allToolsQuery.isLoading) {
    return <div className="workspace-state"><span className="kairo-kicker">OUTILS</span><strong>Lecture du registre MCP…</strong></div>
  }
  if (error) {
    return <div className="workspace-state workspace-state-error"><strong>Impossible de lire le registre d’outils.</strong><span>{error instanceof Error ? error.message : 'Erreur KAIRO Core.'}</span></div>
  }

  return (
    <div className="tools-workspace">
      <aside className="tools-servers">
        <header><div><span className="kairo-kicker">SERVEURS MCP</span><strong>Sources d’outils</strong></div><b>{servers.length}</b></header>
        {servers.length === 0
          ? <div className="workspace-empty"><strong>Aucun serveur MCP enregistré.</strong><span>Le registre reste vide plutôt que de simuler des outils.</span></div>
          : servers.map((server) => <ServerCard key={server.id} server={server} selected={server.key === serverKey} onSelect={() => { setServerKey(server.key); setSelectedToolKey('') }} />)}
        <RegisterServer />
      </aside>

      <section className="tools-main">
        {selectedServer ? (
          <>
            <header className="workspace-title tools-title">
              <div><span className="kairo-kicker">OUTILS</span><h1>{selectedServer.title}</h1><p>{selectedServer.endpoint_url} · namespace {selectedServer.namespace} · génération de catalogue {selectedServer.catalog_generation}</p></div>
              <strong>{tools.filter((tool) => tool.enabled).length}/{tools.length}</strong>
            </header>
            <div className="tools-server-actions">
              <div>
                <i className={selectedServer.enabled ? 'tools-server-live' : ''} />
                <span>{selectedServer.enabled ? 'Serveur autorisé' : 'Serveur désactivé'}</span>
                <small>Catalogue reçu via la passerelle MCP de confiance.</small>
              </div>
              <button type="button" disabled={serverPolicy.isPending} className={selectedServer.enabled ? 'tools-disable-server' : ''} onClick={() => serverPolicy.mutate(!selectedServer.enabled)}>{serverPolicy.isPending ? '…' : selectedServer.enabled ? 'Désactiver' : 'Activer'}</button>
            </div>
            {serverPolicy.isError && <small className="workspace-error">{serverPolicy.error instanceof Error ? serverPolicy.error.message : 'Politique serveur impossible.'}</small>}
            <div className="tools-toolbar">
              <select value={riskFilter} onChange={(event) => setRiskFilter(event.target.value)}><option value="all">Tous risques</option><option value="read">Lecture</option><option value="write">Écriture</option><option value="destructive">Destructif</option></select>
              <select value={availabilityFilter} onChange={(event) => setAvailabilityFilter(event.target.value)}><option value="available">Disponibles</option><option value="enabled">Autorisés</option><option value="all">Tout le catalogue</option></select>
            </div>
            {visibleTools.length === 0
              ? <div className="workspace-empty"><strong>Aucun outil dans ce filtre.</strong><span>{selectedServer.catalog_generation === 0 ? 'Le catalogue n’a pas encore été reçu par KAIRO.' : 'Modifiez le filtre ou vérifiez le dernier catalogue MCP.'}</span></div>
              : <div className="tools-tool-list">{visibleTools.map((tool) => <ToolCard key={tool.id} tool={tool} serverEnabled={selectedServer.enabled} onInspect={() => setSelectedToolKey(tool.key)} />)}</div>}
          </>
        ) : <div className="workspace-empty"><strong>Enregistrez ou sélectionnez un serveur MCP.</strong></div>}
      </section>

      <aside className="tools-inspector">{selectedTool ? <ToolInspector tool={selectedTool} /> : <div className="workspace-empty"><strong>Aucun contrat sélectionné.</strong></div>}</aside>
    </div>
  )
}
