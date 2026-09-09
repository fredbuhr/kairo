import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { KairoGraphEntityRef } from '@kairo/graph'

import {
  decideApproval,
  fetchAgentExecutions,
  fetchApprovalRequests,
  type AgentExecutionRecord,
  type ApprovalRecord,
  type ProjectRecord,
} from '../../lib/api'

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

function money(value?: string | number | null) {
  const parsed = Number(value || 0)
  if (!Number.isFinite(parsed)) return '—'
  if (parsed === 0) return '$0'
  if (parsed < 0.01) return `$${parsed.toFixed(4)}`
  return `$${parsed.toFixed(2)}`
}

function capabilityLabel(value: string) {
  const labels: Record<string, string> = {
    'research.autonomous': 'Research',
    'news.brief': 'News Intelligence',
    'assistant.route.semantic': 'Routage sémantique',
    'document.ingest': 'Indexation document',
    'tool.invoke': 'Outil MCP',
  }
  return labels[value] || value
}

function executionStatus(value: string | null | undefined) {
  const labels: Record<string, string> = {
    pending_start: 'Démarrage',
    pending: 'En attente',
    queued: 'Planifiée',
    running: 'En cours',
    waiting: 'En attente',
    waiting_approval: 'Approbation',
    completed: 'Terminée',
    failed: 'Échec',
    cancelled: 'Annulée',
  }
  return value ? labels[value] || value : 'Sans workflow'
}

function operationalStatus(execution: AgentExecutionRecord) {
  return execution.workflow_status || execution.task_status
}

function isActive(execution: AgentExecutionRecord) {
  return ['pending_start', 'pending', 'queued', 'running', 'waiting', 'waiting_approval', 'in_progress'].includes(operationalStatus(execution))
}

function safeMeta(value: unknown) {
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return null
}

function ExecutionCard({
  execution,
  project,
  onExplore,
}: {
  execution: AgentExecutionRecord
  project?: ProjectRecord
  onExplore: (entity: KairoGraphEntityRef) => void
}) {
  const status = operationalStatus(execution)
  const metadata = Object.entries(execution.metadata)
    .map(([key, value]) => [key, safeMeta(value)] as const)
    .filter((entry): entry is readonly [string, string] => entry[1] !== null)
    .slice(0, 4)

  return (
    <article className={`agent-run agent-run-${status}`}>
      <div className="agent-run-signal"><i /></div>
      <div className="agent-run-body">
        <div className="agent-run-topline">
          <div><span>{capabilityLabel(execution.capability)}</span><strong>{execution.title}</strong></div>
          <b>{executionStatus(status)}</b>
        </div>
        <small>{project?.name || 'Workspace KAIRO'} · autorité A{execution.authority_ceiling} · {shortDateTime(execution.updated_at)}</small>
        {metadata.length > 0 && (
          <div className="agent-run-meta">
            {metadata.map(([key, value]) => <span key={key}><strong>{key.replaceAll('_', ' ')}</strong>{value}</span>)}
          </div>
        )}
        {execution.last_error && <p className="agent-run-error">{execution.last_error}</p>}
        <div className="agent-run-budget">
          <span><strong>{money(execution.spent_usd)}</strong> dépensé</span>
          <span><strong>{execution.budget_usd == null ? '—' : money(execution.budget_usd)}</strong> budget</span>
          {execution.pending_approvals > 0 && <span className="agent-run-approval"><strong>{execution.pending_approvals}</strong> approbation(s)</span>}
        </div>
      </div>
      <div className="agent-run-actions">
        <button type="button" onClick={() => onExplore({ entity_type: 'task', entity_id: execution.task_id })}>Tâche ↗</button>
        {execution.workflow_execution_id && <button type="button" onClick={() => onExplore({ entity_type: 'workflow_execution', entity_id: execution.workflow_execution_id! })}>Workflow ↗</button>}
      </div>
    </article>
  )
}

function ApprovalCard({ approval }: { approval: ApprovalRecord }) {
  const client = useQueryClient()
  const [note, setNote] = useState('')
  const mutation = useMutation({
    mutationFn: (decision: 'approved' | 'denied') => decideApproval(approval.id, decision, note.trim() || undefined),
    onSuccess: async () => {
      setNote('')
      await Promise.all([
        client.invalidateQueries({ queryKey: ['agent-executions'] }),
        client.invalidateQueries({ queryKey: ['approval-requests'] }),
        client.invalidateQueries({ queryKey: ['kairo-graph'] }),
      ])
    },
  })

  return (
    <article className="agent-approval-card">
      <div className="agent-approval-heading">
        <div><span>A{approval.authority_level}</span><strong>{approval.action}</strong></div>
        <small>{shortDateTime(approval.created_at)}</small>
      </div>
      <p>{approval.reason}</p>
      <div className="agent-approval-resource"><span>{approval.resource_type}</span><strong>{approval.resource_id || 'ressource non nommée'}</strong></div>
      <textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Note de décision (optionnelle)" rows={2} />
      <div className="agent-approval-actions">
        <button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate('denied')}>Refuser</button>
        <button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate('approved')}>Approuver</button>
      </div>
      {mutation.isError && <small className="workspace-error">{mutation.error instanceof Error ? mutation.error.message : 'Décision impossible.'}</small>}
    </article>
  )
}

export function AgentsWorkspace({
  projects,
  onExploreEntity,
}: {
  projects: ProjectRecord[]
  onExploreEntity: (entity: KairoGraphEntityRef) => void
}) {
  const [statusFilter, setStatusFilter] = useState('active')
  const [capabilityFilter, setCapabilityFilter] = useState('')
  const executionsQuery = useQuery({
    queryKey: ['agent-executions'],
    queryFn: () => fetchAgentExecutions(120),
    staleTime: 3500,
    refetchInterval: 7000,
  })
  const approvalsQuery = useQuery({
    queryKey: ['approval-requests', 'pending'],
    queryFn: () => fetchApprovalRequests('pending'),
    staleTime: 2500,
    refetchInterval: 7000,
  })
  const executions = executionsQuery.data || []
  const approvals = approvalsQuery.data || []
  const projectsById = useMemo(() => new Map(projects.map((project) => [project.id, project])), [projects])
  const capabilities = useMemo(() => Array.from(new Set(executions.map((execution) => execution.capability))).sort(), [executions])
  const visible = useMemo(() => executions.filter((execution) => {
    if (capabilityFilter && execution.capability !== capabilityFilter) return false
    const status = operationalStatus(execution)
    if (statusFilter === 'active') return isActive(execution)
    if (statusFilter === 'failed') return status === 'failed'
    if (statusFilter === 'completed') return status === 'completed'
    return true
  }), [capabilityFilter, executions, statusFilter])
  const activeCount = executions.filter(isActive).length
  const failedCount = executions.filter((execution) => operationalStatus(execution) === 'failed').length
  const totalSpend = executions.reduce((sum, execution) => sum + Number(execution.spent_usd || 0), 0)
  const error = executionsQuery.error || approvalsQuery.error

  if (executionsQuery.isLoading || approvalsQuery.isLoading) {
    return <div className="workspace-state"><span className="kairo-kicker">AGENTS</span><strong>Lecture des exécutions durables…</strong></div>
  }
  if (error) {
    return <div className="workspace-state workspace-state-error"><strong>Impossible de lire les opérations KAIRO.</strong><span>{error instanceof Error ? error.message : 'Erreur KAIRO Core.'}</span></div>
  }

  return (
    <div className="agents-workspace">
      <section className="agents-main">
        <header className="workspace-title agents-title">
          <div><span className="kairo-kicker">AGENTS & EXÉCUTIONS</span><h1>Ce que KAIRO est en train de faire</h1><p>Cette vue sépare les workflows/agents durables du travail humain. Chaque ligne correspond à une vraie Task de capacité et, lorsqu’il existe, à son WorkflowExecution canonique.</p></div>
          <strong>{activeCount}</strong>
        </header>
        <div className="agents-metrics">
          <span><strong>{activeCount}</strong> actives</span>
          <span><strong>{approvals.length}</strong> approbations</span>
          <span><strong>{failedCount}</strong> échecs</span>
          <span><strong>{money(totalSpend)}</strong> dépense visible</span>
        </div>
        <div className="agents-toolbar">
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="active">Actives</option><option value="all">Toutes</option><option value="completed">Terminées</option><option value="failed">Échecs</option></select>
          <select value={capabilityFilter} onChange={(event) => setCapabilityFilter(event.target.value)}><option value="">Toutes les capacités</option>{capabilities.map((capability) => <option key={capability} value={capability}>{capabilityLabel(capability)}</option>)}</select>
        </div>
        {visible.length === 0 ? (
          <div className="workspace-empty"><strong>Aucune exécution dans ce filtre.</strong><span>Les prochains workflows KAIRO apparaîtront ici sans polluer votre liste de tâches humaines.</span></div>
        ) : (
          <div className="agent-run-list">{visible.map((execution) => <ExecutionCard key={execution.task_id} execution={execution} project={projectsById.get(execution.project_id)} onExplore={onExploreEntity} />)}</div>
        )}
      </section>

      <aside className="agents-approval-rail">
        <header><div><span className="kairo-kicker">À VOTRE ATTENTION</span><strong>Approbations</strong></div><b>{approvals.length}</b></header>
        {approvals.length === 0 ? <div className="agents-no-approval"><i /><span>Aucune action ne demande votre autorisation.</span></div> : approvals.map((approval) => <ApprovalCard key={approval.id} approval={approval} />)}
      </aside>
    </div>
  )
}
