export type KairoGraphNodeProvenance = 'canonical'
export type KairoGraphEdgeProvenance = 'canonical_relationship' | 'canonical_fk'
export type KairoGraphProjectionMode = 'home' | 'neighborhood'
export type KairoGraphQuality = 'auto' | 'high' | 'balanced' | 'eco'

export interface KairoGraphEntityRef {
  entity_type: string
  entity_id: string
}

export interface KairoGraphNode {
  id: string
  entity_type: string
  label: string
  subtitle?: string | null
  project_id?: string | null
  status?: string | null
  importance: number
  activity: number
  recency: number
  relationship_count: number
  cluster_hint?: string | null
  lod: 0 | 1 | 2 | 3
  provenance: KairoGraphNodeProvenance
  metadata: Record<string, unknown>
  updated_at?: string | null
}

export interface KairoGraphEdge {
  id: string
  source: KairoGraphEntityRef
  target: KairoGraphEntityRef
  relation: string
  directed: boolean
  strength: number
  provenance: KairoGraphEdgeProvenance
  explanation?: string | null
  metadata: Record<string, unknown>
}

export interface KairoGraphProjectionContext {
  mode: KairoGraphProjectionMode
  focus?: KairoGraphEntityRef | null
  depth: number
  requested_limit: number
}

export interface KairoGraphProjection {
  context: KairoGraphProjectionContext
  nodes: KairoGraphNode[]
  edges: KairoGraphEdge[]
  truncated: boolean
  generated_at: string
}

export interface KairoGraphSearchResult {
  query: string
  nodes: KairoGraphNode[]
}

export interface KairoGraphPose {
  x: number
  y: number
  z: number
}

export interface KairoGraphVelocity {
  x: number
  y: number
  z: number
}

export interface KairoGraphLayoutNode {
  key: string
  node: KairoGraphNode
  pose: KairoGraphPose
  velocity: KairoGraphVelocity
  radius: number
  opacity: number
  settled: boolean
}

export interface KairoGraphViewportState {
  focusKey?: string | null
  selectedKey?: string | null
  hoveredKey?: string | null
  isolatedKey?: string | null
  semanticZoom: number
  quality: KairoGraphQuality
  reducedMotion: boolean
}

export function graphEntityKey(entity: KairoGraphEntityRef): string {
  return `${entity.entity_type}:${entity.entity_id}`
}

export function graphNodeKey(node: Pick<KairoGraphNode, 'entity_type' | 'id'>): string {
  return `${node.entity_type}:${node.id}`
}
