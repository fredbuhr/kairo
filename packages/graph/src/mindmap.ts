import type {
  KairoGraphEdge,
  KairoGraphEntityRef,
  KairoGraphNode,
  KairoGraphProjection,
} from './types'
import { graphEntityKey, graphNodeKey } from './types'

export interface KairoMindMapOptions {
  rootKey?: string | null
  radialStep?: number
}

export interface KairoMindMapNode {
  key: string
  entity: KairoGraphEntityRef
  node: KairoGraphNode
  x: number
  y: number
  depth: number
  parentKey?: string | null
  connected: boolean
}

export interface KairoMindMapEdge {
  id: string
  sourceKey: string
  targetKey: string
  relation: string
  directed: boolean
  strength: number
  provenance: KairoGraphEdge['provenance']
  explanation?: string | null
}

export interface KairoMindMapProjection {
  rootKey?: string | null
  nodes: KairoMindMapNode[]
  edges: KairoMindMapEdge[]
  maxDepth: number
}

type Neighbor = {
  key: string
  strength: number
}

function scoreNode(node: KairoGraphNode): number {
  const relationshipScore = Math.min(1, node.relationship_count / 12)
  return node.importance * 0.52 + node.activity * 0.16 + node.recency * 0.10 + relationshipScore * 0.22
}

function compareNodeKeys(a: string, b: string, nodes: Map<string, KairoGraphNode>): number {
  const nodeA = nodes.get(a)
  const nodeB = nodes.get(b)
  const scoreA = nodeA ? scoreNode(nodeA) : 0
  const scoreB = nodeB ? scoreNode(nodeB) : 0
  if (scoreA !== scoreB) return scoreB - scoreA
  return a.localeCompare(b)
}

function chooseRoot(projection: KairoGraphProjection, preferred?: string | null): string | null {
  const keys = new Set(projection.nodes.map(graphNodeKey))
  if (preferred && keys.has(preferred)) return preferred

  if (projection.context.focus) {
    const focusKey = graphEntityKey(projection.context.focus)
    if (keys.has(focusKey)) return focusKey
  }

  const ranked = [...projection.nodes].sort((a, b) => {
    const delta = scoreNode(b) - scoreNode(a)
    if (delta !== 0) return delta
    return graphNodeKey(a).localeCompare(graphNodeKey(b))
  })
  return ranked[0] ? graphNodeKey(ranked[0]) : null
}

function buildAdjacency(
  projection: KairoGraphProjection,
  nodeByKey: Map<string, KairoGraphNode>,
): Map<string, Neighbor[]> {
  const adjacency = new Map<string, Map<string, number>>()
  for (const key of nodeByKey.keys()) adjacency.set(key, new Map())

  for (const edge of projection.edges) {
    const source = graphEntityKey(edge.source)
    const target = graphEntityKey(edge.target)
    if (!nodeByKey.has(source) || !nodeByKey.has(target) || source === target) continue

    const sourceNeighbors = adjacency.get(source)!
    const targetNeighbors = adjacency.get(target)!
    sourceNeighbors.set(target, Math.max(sourceNeighbors.get(target) || 0, edge.strength))
    targetNeighbors.set(source, Math.max(targetNeighbors.get(source) || 0, edge.strength))
  }

  const result = new Map<string, Neighbor[]>()
  for (const [key, neighbors] of adjacency) {
    result.set(
      key,
      [...neighbors.entries()]
        .map(([neighborKey, strength]) => ({ key: neighborKey, strength }))
        .sort((a, b) => {
          if (a.strength !== b.strength) return b.strength - a.strength
          return compareNodeKeys(a.key, b.key, nodeByKey)
        }),
    )
  }
  return result
}

export function buildMindMapProjection(
  projection: KairoGraphProjection,
  options: KairoMindMapOptions = {},
): KairoMindMapProjection {
  const radialStep = Math.max(140, options.radialStep || 255)
  const nodeByKey = new Map(projection.nodes.map((node) => [graphNodeKey(node), node]))
  const rootKey = chooseRoot(projection, options.rootKey)

  if (!rootKey) {
    return { rootKey: null, nodes: [], edges: [], maxDepth: 0 }
  }

  const adjacency = buildAdjacency(projection, nodeByKey)
  const depth = new Map<string, number>([[rootKey, 0]])
  const parent = new Map<string, string | null>([[rootKey, null]])
  const queue = [rootKey]

  while (queue.length > 0) {
    const current = queue.shift()!
    const currentDepth = depth.get(current) || 0
    for (const neighbor of adjacency.get(current) || []) {
      if (depth.has(neighbor.key)) continue
      depth.set(neighbor.key, currentDepth + 1)
      parent.set(neighbor.key, current)
      queue.push(neighbor.key)
    }
  }

  const children = new Map<string, string[]>()
  for (const key of nodeByKey.keys()) children.set(key, [])
  for (const [key, parentKey] of parent) {
    if (!parentKey) continue
    children.get(parentKey)?.push(key)
  }
  for (const [key, values] of children) {
    values.sort((a, b) => compareNodeKeys(a, b, nodeByKey))
    children.set(key, values)
  }

  const weightCache = new Map<string, number>()
  const subtreeWeight = (key: string): number => {
    const cached = weightCache.get(key)
    if (cached !== undefined) return cached
    const childKeys = children.get(key) || []
    const weight = childKeys.length === 0
      ? 1
      : Math.max(1, childKeys.reduce((sum, childKey) => sum + subtreeWeight(childKey), 0))
    weightCache.set(key, weight)
    return weight
  }

  const positions = new Map<string, { x: number; y: number }>([[rootKey, { x: 0, y: 0 }]])

  const placeChildren = (key: string, startAngle: number, endAngle: number) => {
    const childKeys = children.get(key) || []
    if (childKeys.length === 0) return
    const totalWeight = childKeys.reduce((sum, childKey) => sum + subtreeWeight(childKey), 0)
    let cursor = startAngle

    childKeys.forEach((childKey, index) => {
      const rawSpan = (endAngle - startAngle) * (subtreeWeight(childKey) / totalWeight)
      const childStart = cursor
      const childEnd = index === childKeys.length - 1 ? endAngle : cursor + rawSpan
      const angle = (childStart + childEnd) / 2
      const childDepth = depth.get(childKey) || 1
      const radius = radialStep * childDepth
      positions.set(childKey, {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
      })
      placeChildren(childKey, childStart, childEnd)
      cursor = childEnd
    })
  }

  placeChildren(rootKey, -Math.PI, Math.PI)

  const connectedDepths = [...depth.values()]
  const connectedMaxDepth = connectedDepths.length ? Math.max(...connectedDepths) : 0
  const disconnected = [...nodeByKey.keys()]
    .filter((key) => !depth.has(key))
    .sort((a, b) => compareNodeKeys(a, b, nodeByKey))

  if (disconnected.length > 0) {
    const outerDepth = connectedMaxDepth + 1
    const radius = radialStep * (outerDepth + 0.35)
    disconnected.forEach((key, index) => {
      const angle = -Math.PI / 2 + (Math.PI * 2 * index) / disconnected.length
      depth.set(key, outerDepth)
      parent.set(key, null)
      positions.set(key, {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
      })
    })
  }

  const maxDepth = [...depth.values()].reduce((current, value) => Math.max(current, value), 0)
  const nodes: KairoMindMapNode[] = [...nodeByKey.entries()]
    .map(([key, node]) => {
      const position = positions.get(key) || { x: 0, y: 0 }
      return {
        key,
        entity: { entity_type: node.entity_type, entity_id: node.id },
        node,
        x: position.x,
        y: position.y,
        depth: depth.get(key) || 0,
        parentKey: parent.get(key) || null,
        connected: key === rootKey || parent.has(key) && parent.get(key) !== null,
      }
    })
    .sort((a, b) => {
      if (a.key === rootKey) return -1
      if (b.key === rootKey) return 1
      if (a.depth !== b.depth) return a.depth - b.depth
      return compareNodeKeys(a.key, b.key, nodeByKey)
    })

  const edges: KairoMindMapEdge[] = projection.edges
    .map((edge) => ({
      id: edge.id,
      sourceKey: graphEntityKey(edge.source),
      targetKey: graphEntityKey(edge.target),
      relation: edge.relation,
      directed: edge.directed,
      strength: edge.strength,
      provenance: edge.provenance,
      explanation: edge.explanation,
    }))
    .filter((edge) => nodeByKey.has(edge.sourceKey) && nodeByKey.has(edge.targetKey))
    .sort((a, b) => a.id.localeCompare(b.id))

  return { rootKey, nodes, edges, maxDepth }
}
