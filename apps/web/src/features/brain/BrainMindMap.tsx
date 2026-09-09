import { useEffect, useMemo } from 'react'
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  useNodesState,
  type Edge,
  type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  buildMindMapProjection,
  graphNodeKey,
  type KairoGraphNode,
  type KairoGraphProjection,
} from '@kairo/graph'

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
    done: 'Terminé',
    failed: 'Échec',
    archived: 'Archivé',
  }
  return status ? labels[status] || status : null
}

function typeClass(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9_-]+/g, '-')
}

export function BrainMindMap({
  projection,
  selectedKey,
  onSelect,
  onExplore,
}: {
  projection: KairoGraphProjection
  selectedKey: string | null
  onSelect: (node: KairoGraphNode | null) => void
  onExplore: (node: KairoGraphNode) => void
}) {
  const mindMap = useMemo(
    () => buildMindMapProjection(projection),
    [projection],
  )
  const nodeByKey = useMemo(
    () => new Map(projection.nodes.map((node) => [graphNodeKey(node), node])),
    [projection],
  )
  const root = mindMap.rootKey ? nodeByKey.get(mindMap.rootKey) || null : null

  const renderedNodes = useMemo<Node[]>(() => mindMap.nodes.map((item) => {
    const selected = item.key === selectedKey
    const rootNode = item.key === mindMap.rootKey
    const width = Math.round(144 + item.node.importance * 54)
    return {
      id: item.key,
      position: { x: item.x - width / 2, y: item.y - 34 },
      selected,
      draggable: true,
      connectable: false,
      className: [
        'brain-map-node',
        `brain-map-type-${typeClass(item.node.entity_type)}`,
        rootNode ? 'brain-map-root' : '',
        selected ? 'brain-map-selected' : '',
        item.connected ? '' : 'brain-map-disconnected',
      ].filter(Boolean).join(' '),
      style: { width },
      data: {
        label: (
          <div className="brain-map-node-content">
            <div className="brain-map-node-topline">
              <span>{entityLabel(item.node.entity_type)}</span>
              <i />
            </div>
            <strong>{item.node.label}</strong>
            <small>
              {statusLabel(item.node.status) || `${item.node.relationship_count} lien${item.node.relationship_count === 1 ? '' : 's'}`}
            </small>
          </div>
        ),
      },
    }
  }), [mindMap, selectedKey])

  const renderedEdges = useMemo<Edge[]>(() => mindMap.edges.map((edge) => {
    const selected = Boolean(selectedKey && (edge.sourceKey === selectedKey || edge.targetKey === selectedKey))
    return {
      id: edge.id,
      source: edge.sourceKey,
      target: edge.targetKey,
      type: 'bezier',
      className: [
        'brain-map-edge',
        edge.provenance === 'canonical_relationship' ? 'brain-map-edge-explicit' : 'brain-map-edge-structural',
        selected ? 'brain-map-edge-selected' : '',
      ].filter(Boolean).join(' '),
      label: selected ? edge.relation.replaceAll('_', ' ') : undefined,
      markerEnd: edge.directed ? { type: MarkerType.ArrowClosed } : undefined,
      zIndex: selected ? 4 : 1,
    }
  }), [mindMap.edges, selectedKey])

  const [nodes, setNodes, onNodesChange] = useNodesState(renderedNodes)

  useEffect(() => {
    setNodes((current) => {
      const positions = new Map(current.map((node) => [node.id, node.position]))
      return renderedNodes.map((node) => ({
        ...node,
        position: positions.get(node.id) || node.position,
      }))
    })
  }, [renderedNodes, setNodes])

  const contextKey = [
    projection.context.mode,
    projection.context.focus?.entity_type || 'root',
    projection.context.focus?.entity_id || 'root',
    projection.nodes.length,
    projection.edges.length,
  ].join(':')

  return (
    <section className="brain-mind-map" aria-label="Carte mentale canonique KAIRO">
      <div className="brain-map-heading">
        <div>
          <span className="kairo-kicker">CARTE 2D · PROJECTION CANONIQUE</span>
          <strong>{root?.label || 'Cerveau KAIRO'}</strong>
          <small>Double-cliquez pour ouvrir le voisinage. Le déplacement des cartes reste purement visuel.</small>
        </div>
        <div className="brain-map-stats">
          <span>{mindMap.nodes.length} entités</span>
          <span>{mindMap.edges.length} relations</span>
          <span>{mindMap.maxDepth} niveaux</span>
        </div>
      </div>

      <ReactFlow
        key={contextKey}
        nodes={nodes}
        edges={renderedEdges}
        onNodesChange={onNodesChange}
        onNodeClick={(_, reactNode) => onSelect(nodeByKey.get(reactNode.id) || null)}
        onNodeDoubleClick={(_, reactNode) => {
          const node = nodeByKey.get(reactNode.id)
          if (node) onExplore(node)
        }}
        onPaneClick={() => onSelect(null)}
        nodesConnectable={false}
        fitView
        fitViewOptions={{ padding: 0.22, maxZoom: 1.15 }}
        minZoom={0.16}
        maxZoom={1.8}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={34} size={1} />
        <MiniMap pannable zoomable nodeStrokeWidth={2} />
        <Controls showInteractive={false} />
      </ReactFlow>

      <div className="brain-map-legend" aria-hidden="true">
        <span><i className="brain-map-legend-explicit" /> relation explicite</span>
        <span><i className="brain-map-legend-structural" /> structure canonique</span>
      </div>
    </section>
  )
}
