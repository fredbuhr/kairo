export interface KairoGraphNode {
  id: string
  entityType: string
  label: string
  projectId?: string
}

export interface KairoGraphEdge {
  id: string
  source: string
  target: string
  relation: string
  directed: boolean
}

export interface KairoGraphSnapshot {
  nodes: KairoGraphNode[]
  edges: KairoGraphEdge[]
}
