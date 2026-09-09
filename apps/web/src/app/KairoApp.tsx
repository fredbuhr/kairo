import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  MyceliumViewport,
  filterGraphProjection,
  graphEntityKey,
  graphNodeKey,
  isolateGraphProjection,
  type KairoGraphEntityRef,
  type KairoGraphNode,
  type KairoGraphQuality,
  type KairoGraphTooltipPoint,
} from '@kairo/graph'

import { AssistantDrawer } from '../features/assistant/AssistantDrawer'
import { useAssistant } from '../features/assistant/useAssistant'
import { CoreWorkspace, type CoreWorkspaceMode } from '../features/core/CoreWorkspaces'
import {
  fetchGraphHome,
  fetchGraphNeighborhood,
  resolveGraphDirective,
  searchGraph,
} from '../lib/api'

type ViewMode = 'home' | 'brain'

type NavigationItem = {
  key: string
  label: string
  glyph: string
  available: boolean
}

const NAVIGATION: NavigationItem[] = [
  { key: 'home', label: 'Accueil', glyph: '⌂', available: true },
  { key: 'assistant', label: 'Assistant', glyph: '◌', available: true },
  { key: 'projects', label: 'Projets', glyph: '◇', available: true },
  { key: 'knowledge', label: 'Connaissances', glyph: '□', available: true },
  { key: 'brain', label: 'Cerveau KAIRO', glyph: '◎', available: true },
  { key: 'tasks', label: 'Tâches', glyph: '✓', available: true },
  { key: 'calendar', label: 'Calendrier', glyph: '▦', available: true },
  { key: 'agents', label: 'Agents', glyph: '⌘', available: true },
  { key: 'automations', label: 'Automatisations', glyph: '↯', available: false },
  { key: 'finance', label: 'Finance & Crypto', glyph: '◒', available: false },
  { key: 'tools', label: 'Outils', glyph: '⊹', available: false },
  { key: 'settings', label: 'Paramètres', glyph: '⚙', available: true },
]

function useReducedMotionPreference() {
  const [reduced, setReduced] = useState(false)
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReduced(media.matches)
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  return reduced
}

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

function KairoMark({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`kairo-mark ${compact ? 'kairo-mark-compact' : ''}`} aria-hidden="true">
      <i />
      <i />
      <i />
      <i />
    </span>
  )
}

function ContextRail({
  projection,
  selected,
  selectedKey,
  isolatedKey,
  collapsed,
  onToggle,
  onExplore,
  onToggleIsolation,
}: {
  projection: Awaited<ReturnType<typeof fetchGraphHome>> | undefined
  selected: KairoGraphNode | null
  selectedKey: string | null
  isolatedKey: string | null
  collapsed: boolean
  onToggle: () => void
  onExplore: (node: KairoGraphNode) => void
  onToggleIsolation: (key: string) => void
}) {
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

export default function KairoApp() {
  const assistant = useAssistant()
  const systemReducedMotion = useReducedMotionPreference()
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('home')
  const [workspaceMode, setWorkspaceMode] = useState<CoreWorkspaceMode | null>(null)
  const [focus, setFocus] = useState<KairoGraphEntityRef | null>(null)
  const [history, setHistory] = useState<Array<KairoGraphEntityRef | null>>([])
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [isolatedKey, setIsolatedKey] = useState<string | null>(null)
  const [hiddenEntityTypes, setHiddenEntityTypes] = useState<string[]>([])
  const [hiddenRelations, setHiddenRelations] = useState<string[]>([])
  const [hovered, setHovered] = useState<{ node: KairoGraphNode; point: KairoGraphTooltipPoint } | null>(null)
  const [contextCollapsed, setContextCollapsed] = useState(false)
  const [quality, setQuality] = useState<KairoGraphQuality>('auto')
  const [forceReducedMotion, setForceReducedMotion] = useState(false)
  const [listView, setListView] = useState(false)
  const [search, setSearch] = useState('')
  const reducedMotion = systemReducedMotion || forceReducedMotion

  const graphQuery = useQuery({
    queryKey: ['kairo-graph', viewMode, focus?.entity_type || 'root', focus?.entity_id || 'root'],
    queryFn: () => focus
      ? fetchGraphNeighborhood(focus, viewMode === 'brain' ? 2 : 1, viewMode === 'brain' ? 150 : 96)
      : fetchGraphHome(viewMode === 'brain' ? 140 : 72),
    refetchInterval: focus ? false : 30000,
    staleTime: 7000,
  })

  const searchQuery = useQuery({
    queryKey: ['kairo-graph-search', search.trim()],
    queryFn: () => searchGraph(search.trim()),
    enabled: search.trim().length >= 2,
    staleTime: 15000,
  })

  const projection = graphQuery.data
  const availableEntityTypes = useMemo(
    () => Array.from(new Set(projection?.nodes.map((node) => node.entity_type) || [])).sort(),
    [projection],
  )
  const availableRelations = useMemo(
    () => Array.from(new Set(projection?.edges.map((edge) => edge.relation) || [])).sort(),
    [projection],
  )
  const displayProjection = useMemo(() => {
    if (!projection) return undefined
    const preserved = [selectedKey, focus ? graphEntityKey(focus) : null].filter((value): value is string => Boolean(value))
    const filtered = filterGraphProjection(projection, {
      hiddenEntityTypes,
      hiddenRelations,
      preserveKeys: preserved,
    })
    return isolateGraphProjection(filtered, isolatedKey, 1)
  }, [focus, hiddenEntityTypes, hiddenRelations, isolatedKey, projection, selectedKey])
  const selected = useMemo(
    () => projection?.nodes.find((node) => graphNodeKey(node) === selectedKey) || null,
    [projection, selectedKey],
  )

  useEffect(() => {
    if (assistant.brief?.status === 'completed' || assistant.research?.status === 'completed') {
      void graphQuery.refetch()
    }
  }, [assistant.brief?.status, assistant.research?.status])

  function toggleHidden(value: string, setter: React.Dispatch<React.SetStateAction<string[]>>) {
    setter((current) => current.includes(value) ? current.filter((item) => item !== value) : [...current, value])
  }

  function clearFilters() {
    setHiddenEntityTypes([])
    setHiddenRelations([])
  }

  function focusEntity(entity: KairoGraphEntityRef, isolate = false) {
    const key = graphEntityKey(entity)
    setWorkspaceMode(null)
    setHistory((current) => [...current, focus])
    setFocus(entity)
    setSelectedKey(key)
    setIsolatedKey(isolate ? key : null)
    setSearch('')
    setFiltersOpen(false)
  }

  function explore(node: KairoGraphNode) {
    focusEntity({ entity_type: node.entity_type, entity_id: node.id })
  }

  function goBack() {
    setIsolatedKey(null)
    setHistory((current) => {
      if (current.length === 0) {
        setFocus(null)
        setSelectedKey(null)
        return current
      }
      const copy = [...current]
      const previous = copy.pop() ?? null
      setFocus(previous)
      setSelectedKey(previous ? graphEntityKey(previous) : null)
      return copy
    })
  }

  function recenter(mode: ViewMode = viewMode) {
    setWorkspaceMode(null)
    setViewMode(mode)
    setFocus(null)
    setHistory([])
    setSelectedKey(null)
    setIsolatedKey(null)
  }

  function openWorkspace(mode: CoreWorkspaceMode) {
    setWorkspaceMode(mode)
    setFiltersOpen(false)
    setAssistantOpen(false)
    setSearch('')
  }

  function activateNavigation(item: NavigationItem) {
    if (!item.available) return
    if (item.key === 'home') recenter('home')
    if (item.key === 'brain') recenter('brain')
    if (['projects', 'tasks', 'knowledge', 'calendar', 'agents'].includes(item.key)) openWorkspace(item.key as CoreWorkspaceMode)
    if (item.key === 'assistant') setAssistantOpen(true)
    if (item.key === 'settings') setSettingsOpen(true)
  }

  async function submitCommand(event: FormEvent) {
    event.preventDefault()
    const text = assistant.command.trim()
    if (!text) return

    try {
      const resolution = await resolveGraphDirective(text)
      if (resolution.outcome === 'directive' && resolution.directive) {
        focusEntity(
          resolution.directive.entity,
          resolution.directive.kind === 'isolate_entity',
        )
        assistant.setCommand('')
        setAssistantOpen(false)
        return
      }
      if (resolution.outcome === 'ambiguous' || resolution.outcome === 'not_found') {
        setWorkspaceMode(null)
        setSearch(resolution.query)
        assistant.setCommand('')
        setAssistantOpen(false)
        return
      }
    } catch {
      // Spatial navigation is a progressive deterministic front door. If it is unavailable,
      // preserve the user's request and continue through the canonical Command Kernel.
    }

    setAssistantOpen(true)
    await assistant.sendCommand()
  }

  const searchResults = search.trim().length >= 2 ? searchQuery.data?.nodes || [] : []
  const activeNavigation = workspaceMode || (viewMode === 'brain' ? 'brain' : 'home')
  const activeFilterCount = hiddenEntityTypes.length + hiddenRelations.length
  const workspaceLabel = workspaceMode === 'projects'
    ? 'Projets'
    : workspaceMode === 'tasks'
      ? 'Tâches'
      : workspaceMode === 'knowledge'
        ? 'Connaissances'
        : workspaceMode === 'calendar'
          ? 'Calendrier'
          : workspaceMode === 'agents'
            ? 'Agents'
            : null

  return (
    <main className="kairo-app">
      <aside className="primary-nav">
        <div className="brand-lockup" title="Un esprit plus calme pour un demain plus lumineux.">
          <KairoMark />
          <div><strong>KAIRO</strong><span>PENSER · RELIER · AVANCER</span></div>
        </div>

        <nav aria-label="Navigation KAIRO">
          {NAVIGATION.map((item, index) => (
            <button
              key={item.key}
              type="button"
              onClick={() => activateNavigation(item)}
              disabled={!item.available}
              className={`${activeNavigation === item.key ? 'nav-active' : ''} ${index === NAVIGATION.length - 3 ? 'nav-section-start' : ''}`}
              title={item.available ? item.label : `${item.label} — module à venir`}
            >
              <span className="nav-glyph" aria-hidden="true">{item.glyph}</span>
              <span>{item.label}</span>
              {!item.available && <i className="nav-unavailable" />}
            </button>
          ))}
        </nav>

        <div className="nav-motto">
          <i />
          <p>Des liens plus clairs.<br />Un esprit plus calme.</p>
        </div>
      </aside>

      <section className="spatial-shell">
        <header className="top-bar">
          <div className="spatial-breadcrumbs">
            {workspaceMode ? (
              <span>{workspaceLabel}</span>
            ) : history.length > 0 || focus ? (
              <button type="button" onClick={goBack} className="ghost-button">← Retour</button>
            ) : (
              <span>{viewMode === 'brain' ? 'Cerveau KAIRO' : 'Accueil'}</span>
            )}
            {!workspaceMode && focus && selected && <strong>{selected.label}</strong>}
          </div>

          <div className="universal-search">
            <span aria-hidden="true">⌕</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Rechercher dans KAIRO…"
              aria-label="Rechercher dans KAIRO"
            />
            {search.trim().length >= 2 && (
              <div className="search-results">
                {searchQuery.isFetching && <small>Recherche…</small>}
                {!searchQuery.isFetching && searchResults.length === 0 && <small>Aucun résultat canonique.</small>}
                {searchResults.map((node) => (
                  <button type="button" key={graphNodeKey(node)} onClick={() => explore(node)}>
                    <span>{node.label}</span>
                    <small>{entityLabel(node.entity_type)}{node.status ? ` · ${statusLabel(node.status)}` : ''}</small>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="top-actions">
            {!workspaceMode && (
              <>
                <button
                  type="button"
                  className={`view-toggle ${filtersOpen || activeFilterCount > 0 ? 'view-toggle-active' : ''}`}
                  onClick={() => setFiltersOpen((value) => !value)}
                  aria-expanded={filtersOpen}
                >
                  Filtres{activeFilterCount > 0 ? ` · ${activeFilterCount}` : ''}
                </button>
                <button type="button" className={`view-toggle ${listView ? 'view-toggle-active' : ''}`} onClick={() => setListView((value) => !value)}>
                  {listView ? '3D' : 'Liste'}
                </button>
              </>
            )}
            <button type="button" className="round-button" onClick={() => setSettingsOpen(true)} aria-label="Qualité et accessibilité">◐</button>
            <button type="button" className="round-button kairo-avatar" onClick={() => setAssistantOpen(true)} aria-label="Ouvrir KAIRO"><KairoMark compact /></button>

            {!workspaceMode && filtersOpen && (
              <section className="graph-filter-panel" aria-label="Filtres du cerveau KAIRO">
                <header>
                  <div><span className="kairo-kicker">VISIBILITÉ</span><strong>Filtrer temporairement</strong></div>
                  <button type="button" onClick={clearFilters} disabled={activeFilterCount === 0}>Réinitialiser</button>
                </header>
                {availableEntityTypes.length > 0 && (
                  <div className="graph-filter-group">
                    <span>Entités</span>
                    <div className="graph-filter-chips">
                      {availableEntityTypes.map((type) => (
                        <label key={type} className={hiddenEntityTypes.includes(type) ? 'graph-filter-muted' : ''}>
                          <input
                            type="checkbox"
                            checked={!hiddenEntityTypes.includes(type)}
                            onChange={() => toggleHidden(type, setHiddenEntityTypes)}
                          />
                          <span>{entityLabel(type)}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}
                {availableRelations.length > 0 && (
                  <div className="graph-filter-group">
                    <span>Relations</span>
                    <div className="graph-filter-chips">
                      {availableRelations.map((relation) => (
                        <label key={relation} className={hiddenRelations.includes(relation) ? 'graph-filter-muted' : ''}>
                          <input
                            type="checkbox"
                            checked={!hiddenRelations.includes(relation)}
                            onChange={() => toggleHidden(relation, setHiddenRelations)}
                          />
                          <span>{relation.replaceAll('_', ' ')}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}
          </div>
        </header>

        <div className="spatial-stage">
          {workspaceMode ? (
            <div className="core-workspace-surface">
              <CoreWorkspace mode={workspaceMode} onExploreEntity={(entity) => focusEntity(entity)} />
            </div>
          ) : (
            <>
              {!listView && (
                <MyceliumViewport
                  projection={displayProjection || null}
                  selectedKey={selectedKey}
                  quality={quality}
                  reducedMotion={reducedMotion}
                  className="mycelium-viewport"
                  onSelect={(node) => setSelectedKey(node ? graphNodeKey(node) : null)}
                  onExplore={explore}
                  onHover={(node, point) => setHovered(node && point ? { node, point } : null)}
                />
              )}

              {listView && (
                <div className="accessible-graph" aria-label="Vue accessible du graphe KAIRO">
                  <header>
                    <span className="kairo-kicker">PROJECTION CANONIQUE</span>
                    <h1>{focus && selected ? selected.label : viewMode === 'brain' ? 'Cerveau KAIRO' : 'Votre univers KAIRO'}</h1>
                    <p>Mêmes entités et mêmes relations que la vue spatiale, présentées sans dépendre du mouvement ou de la profondeur.</p>
                  </header>
                  <div className="accessible-node-list">
                    {displayProjection?.nodes.map((node) => (
                      <button key={graphNodeKey(node)} type="button" onClick={() => setSelectedKey(graphNodeKey(node))} onDoubleClick={() => explore(node)}>
                        <span className="node-type-dot" />
                        <div><strong>{node.label}</strong><small>{entityLabel(node.entity_type)}{node.status ? ` · ${statusLabel(node.status)}` : ''} · {node.relationship_count} liens</small></div>
                        <span>›</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {graphQuery.isLoading && (
                <div className="stage-state"><KairoMark /><span>Construction de votre contexte…</span></div>
              )}
              {graphQuery.isError && (
                <div className="stage-state stage-error"><strong>Le cerveau KAIRO n’est pas disponible.</strong><span>{graphQuery.error instanceof Error ? graphQuery.error.message : 'Erreur de projection.'}</span><button type="button" onClick={() => void graphQuery.refetch()}>Réessayer</button></div>
              )}
              {!graphQuery.isLoading && !graphQuery.isError && displayProjection?.nodes.length === 0 && (
                <div className="stage-state stage-empty"><KairoMark /><strong>Votre univers KAIRO est encore calme.</strong><span>Les projets, tâches, documents et relations réels apparaîtront ici à mesure qu’ils sont créés.</span></div>
              )}

              {hovered && !listView && (
                <div className="node-tooltip" style={{ left: hovered.point.x + 16, top: hovered.point.y + 14 }}>
                  <small>{entityLabel(hovered.node.entity_type)}</small>
                  <strong>{hovered.node.label}</strong>
                  <span>{hovered.node.relationship_count} lien{hovered.node.relationship_count === 1 ? '' : 's'}</span>
                </div>
              )}

              <div className="stage-caption">
                <span>{displayProjection?.nodes.length || 0} entités · {displayProjection?.edges.length || 0} relations</span>
                {isolatedKey && <span>Branche isolée · profondeur 1</span>}
                {activeFilterCount > 0 && <span>{activeFilterCount} filtre{activeFilterCount === 1 ? '' : 's'} actif{activeFilterCount === 1 ? '' : 's'}</span>}
                {displayProjection?.truncated && <span>Projection contextuelle · réseau plus vaste</span>}
              </div>
            </>
          )}
        </div>

        {!workspaceMode && (
          <ContextRail
            projection={displayProjection}
            selected={selected}
            selectedKey={selectedKey}
            isolatedKey={isolatedKey}
            collapsed={contextCollapsed}
            onToggle={() => setContextCollapsed((value) => !value)}
            onExplore={explore}
            onToggleIsolation={(key) => setIsolatedKey((current) => current === key ? null : key)}
          />
        )}

        <form className="command-dock" onSubmit={submitCommand}>
          <button type="button" className="dock-kairo" onClick={() => setAssistantOpen(true)} aria-label="Ouvrir la conversation KAIRO"><KairoMark compact /></button>
          <div className="dock-input">
            <span aria-hidden="true">◌</span>
            <input
              value={assistant.command}
              onChange={(event) => assistant.setCommand(event.target.value)}
              placeholder="Demandez à KAIRO…"
              aria-label="Demander à KAIRO"
            />
          </div>
          <button type="submit" className="dock-send" disabled={assistant.busy || !assistant.command.trim()}>{assistant.busy ? '···' : '↑'}</button>
          <button type="button" className="dock-thread" onClick={() => setAssistantOpen(true)}>Conversation</button>
        </form>

        <AssistantDrawer assistant={assistant} open={assistantOpen} onClose={() => setAssistantOpen(false)} />

        {settingsOpen && (
          <div className="settings-backdrop" role="presentation" onMouseDown={() => setSettingsOpen(false)}>
            <section className="settings-panel" role="dialog" aria-modal="true" aria-label="Affichage KAIRO" onMouseDown={(event) => event.stopPropagation()}>
              <header><div><span className="kairo-kicker">AFFICHAGE</span><h2>Qualité et mouvement</h2></div><button type="button" className="icon-button" onClick={() => setSettingsOpen(false)}>×</button></header>
              <label>
                <span>Qualité graphique</span>
                <select value={quality} onChange={(event) => setQuality(event.target.value as KairoGraphQuality)}>
                  <option value="auto">Automatique</option>
                  <option value="high">Haute</option>
                  <option value="balanced">Équilibrée</option>
                  <option value="eco">Économie</option>
                </select>
              </label>
              <label className="settings-check">
                <input type="checkbox" checked={forceReducedMotion} onChange={(event) => setForceReducedMotion(event.target.checked)} />
                <span><strong>Réduire les animations</strong><small>Les respirations et impulsions non essentielles sont fortement limitées.</small></span>
              </label>
              {systemReducedMotion && <p className="settings-note">Votre système demande déjà une réduction des mouvements. KAIRO respecte cette préférence.</p>}
            </section>
          </div>
        )}
      </section>
    </main>
  )
}
