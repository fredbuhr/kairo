import type { KairoGraphProjection } from './types'
import { graphEntityKey, graphNodeKey } from './types'

export function isolateGraphProjection(
  projection: KairoGraphProjection,
  rootKey: string | null | undefined,
  depth = 1,
): KairoGraphProjection {
  if (!rootKey || depth < 1) return projection

  const available = new Set(projection.nodes.map(graphNodeKey))
  if (!available.has(rootKey)) return projection

  const visible = new Set<string>([rootKey])
  let frontier = new Set<string>([rootKey])

  for (let level = 0; level < depth && frontier.size > 0; level += 1) {
    const next = new Set<string>()
    for (const edge of projection.edges) {
      const source = graphEntityKey(edge.source)
      const target = graphEntityKey(edge.target)
      if (frontier.has(source) && available.has(target) && !visible.has(target)) next.add(target)
      if (frontier.has(target) && available.has(source) && !visible.has(source)) next.add(source)
    }
    for (const key of next) visible.add(key)
    frontier = next
  }

  const nodes = projection.nodes.filter((node) => visible.has(graphNodeKey(node)))
  const edges = projection.edges.filter(
    (edge) => visible.has(graphEntityKey(edge.source)) && visible.has(graphEntityKey(edge.target)),
  )

  return {
    ...projection,
    nodes,
    edges,
    truncated: projection.truncated || nodes.length < projection.nodes.length,
  }
}
