import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  graphEntityKey,
  graphNodeKey,
  type KairoGraphEntityRef,
  type KairoGraphNode,
  type KairoGraphProjection,
} from '@kairo/graph'

import { fetchToday, type TaskRecord } from '../../lib/api'

function entityLabel(type: string) {
  const labels: Record<string, string> = {
    project: 'Projet',
    task: 'Tâche',
    document: 'Document',
    conversation: 'Conversation',
    approval: 'Approbation',
    artifact: 'Artefact',
    asset: 'Fichier',
    workflow_execution: 'Exécution',
  }
  return labels[type] || type.replaceAll('_', ' ')
}

function statusLabel(status?: string | null) {
  const labels: Record<string, string> = {
    active: 'Actif',
    pending: 'En attente',
    running: 'En cours',
    in_progress: 'En cours',
    queued: 'Planifié',
    blocked: 'Bloqué',
    waiting: 'En attente',
    waiting_approval: 'Approbation requise',
    completed: 'Terminé',
    failed: 'Échec',
  }
  return status ? labels[status] || status : null
}

type TodayItem = {
  task: TaskRecord
  kind: 'overdue' | 'due' | 'planned' | 'important'
  hint: string
}

function useTodayItems() {
  const query = useQuery({
    queryKey: ['today'],
    queryFn: fetchToday,
    staleTime: 30_000,
    refetchInterval: 60_000,
  })
  const items = useMemo<TodayItem[]>(() => {
    const today = query.data
    if (!today) return []
    return [
      ...today.overdue.map((task) => ({ task, kind: 'overdue' as const, hint: 'En retard' })),
      ...today.due_today.map((task) => ({ task, kind: 'due' as const, hint: 'Échéance aujourd’hui' })),
      ...today.planned_today.map((task) => ({ task, kind: 'planned' as const, hint: 'Prévue aujourd’hui' })),
      ...today.important.map((task) => ({ task, kind: 'important' as const, hint: 'Priorité haute' })),
    ]
  }, [query.data])
  return { ...query, items, total: items.length }
}

export function ContextRail({
  projection,
  selected,
  selectedKey,
  isolatedKey,
  collapsed,
  onToggle,
  onExplore,
  onExploreEntity,
  onToggleIsolation,
}: {
  projection: KairoGraphProjection | undefined
  selected: KairoGraphNode | null
  selectedKey: string | null
  isolatedKey: string | null
  collapsed: boolean
  onToggle: () => void
  onExplore: (node: KairoGraphNode) => void
  onExploreEntity: (entity: KairoGraphEntityRef) => void
  onToggleIsolation: (key: string) => void
}) {
  const today = useTodayItems()
  const approvals = projection?.nodes.filter((node) => node.entity_type === 'approval' && node.status === 'pending').slice(0, 4) || []
  const active = projection?.nodes
    .filter((node) => ['task', 'workflow_execution'].includes(node.entity_type) && ['running', 'in_progress', 'queued', 'waiting'].includes(node.status || ''))
    .slice(0, 5) || []
  const relatedEdges = selectedKey
    ? projection?.edges.filter((edge) => graphEntityKey(edge.source) === selectedKey || graphEntityKey(edge.target) === selectedKey).slice(0, 6) || []
    : []

  return (
    <aside className={`context-rail ${collapsed ? 'context-rail-collapsed' : ''}`}>
      <button type="button" className="context-toggle" onClick={onToggle} aria-label={collapsed ? 'Ouvrir le contexte' : 'Fermer le contexte'}>
        {collapsed ? '‹' : '›'}
      </button>
      {!collapsed && (
        <div className="context-scroll">
          {selected && selectedKey && (
            <section className="context-card context-selection">
              <span className="context-eyebrow">{entityLabel(selected.entity_type)}</span>
              <h2>{selected.label}</h2>
              {selected.subtitle && <p>{selected.subtitle}</p>}
              <div className="context-meta">
                {selected.status && <span>{statusLabel(selected.status)}</span>}
                <span>{selected.relationship_count} lien{selected.relationship_count === 1 ? '' : 's'}</span>
              </div>
              <div className="context-actions">
                <button type="button" className="context-primary" onClick={() => onExplore(selected)}>Explorer</button>
                <button
                  type="button"
                  className={`context-secondary ${isolatedKey === selectedKey ? 'context-secondary-active' : ''}`}
                  onClick={() => onToggleIsolation(selectedKey)}
                >
                  {isolatedKey === selectedKey ? 'Afficher tout' : 'Isoler la branche'}
                </button>
              </div>
              {relatedEdges.length > 0 && (
                <div className="context-relations">
                  <strong>Relations visibles</strong>
                  {relatedEdges.map((edge) => (
                    <div key={edge.id}>
                      <span>{edge.relation.replaceAll('_', ' ')}</span>
                      <small>{edge.explanation || edge.provenance}</small>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          <section className="context-card context-today">
            <header className="context-card-heading">
              <span>Aujourd’hui</span>
              {today.total > 0 && <b>{today.total}</b>}
            </header>
            {today.isLoading ? (
              <p className="context-empty">Lecture de votre journée…</p>
            ) : today.isError ? (
              <p className="context-empty">La projection Aujourd’hui n’est pas disponible.</p>
            ) : today.items.length === 0 ? (
              <p className="context-empty">Rien n’est explicitement prévu ou urgent aujourd’hui.</p>
            ) : (
              <div className="context-list context-today-list">
                {today.items.slice(0, 5).map(({ task, kind, hint }) => (
                  <button type="button" key={task.id} onClick={() => onExploreEntity({ entity_type: 'task', entity_id: task.id })}>
                    <i className={`today-dot today-dot-${kind}`} />
                    <span><strong>{task.title}</strong><small>{hint}</small></span>
                  </button>
                ))}
              </div>
            )}
          </section>

          <section className="context-card">
            <header className="context-card-heading">
              <span>À votre attention</span>
              {approvals.length > 0 && <b>{approvals.length}</b>}
            </header>
            {approvals.length === 0 ? (
              <p className="context-empty">Aucune approbation en attente dans la projection actuelle.</p>
            ) : (
              <div className="context-list">
                {approvals.map((node) => (
                  <button type="button" key={graphNodeKey(node)} onClick={() => onExplore(node)}>
                    <i className="attention-dot" />
                    <span><strong>{node.label}</strong><small>{node.subtitle || 'Approbation'}</small></span>
                  </button>
                ))}
              </div>
            )}
          </section>

          {active.length > 0 && (
            <section className="context-card">
              <header className="context-card-heading"><span>Activité KAIRO</span></header>
              <div className="context-list">
                {active.map((node) => (
                  <button type="button" key={graphNodeKey(node)} onClick={() => onExplore(node)}>
                    <i className="activity-dot" />
                    <span><strong>{node.label}</strong><small>{statusLabel(node.status) || entityLabel(node.entity_type)}</small></span>
                  </button>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </aside>
  )
}
