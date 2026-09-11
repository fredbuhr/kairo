export interface NevoliumGraphNode {
  id: string
  entityType: string
  label: string
  projectId?: string
}

export interface NevoliumGraphEdge {
  id: string
  source: string
  target: string
  relation: string
  directed: boolean
}

export interface NevoliumGraphSnapshot {
  nodes: NevoliumGraphNode[]
  edges: NevoliumGraphEdge[]
}
