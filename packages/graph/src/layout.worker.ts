/// <reference lib="webworker" />

import type { KairoGraphEdge, KairoGraphNode, KairoGraphPose } from './types'
import { graphEntityKey, graphNodeKey } from './types'

type LayoutRequest = {
  id: number
  nodes: KairoGraphNode[]
  edges: KairoGraphEdge[]
  focusKey?: string | null
  initialPoses?: Array<[string, KairoGraphPose]>
  warmStart?: boolean
}

type LayoutResponse = {
  id: number
  poses: Array<[string, KairoGraphPose]>
}

type Particle = {
  key: string
  x: number
  y: number
  z: number
  vx: number
  vy: number
  vz: number
  importance: number
  cluster: string
  pinned: boolean
}

function hash(value: string): number {
  let h = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    h ^= value.charCodeAt(index)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function signed(seed: string, salt: number): number {
  const value = hash(`${seed}:${salt}`) / 0xffffffff
  return value * 2 - 1
}

function clusterForNode(node: KairoGraphNode): string {
  // Only canonical/contextual cluster hints may create a shared gravity well. Falling back to
  // entity type would turn the spatial model into a disguised category menu. Unscoped entities
  // therefore receive a stable private well and are grouped by their real relationships instead.
  return node.cluster_hint || node.project_id || graphNodeKey(node)
}

function clusterCenter(cluster: string, anchoredCluster?: string | null): [number, number, number] {
  if (!cluster || cluster === anchoredCluster) return [0, 0, 0]
  const angle = ((hash(cluster) % 10000) / 10000) * Math.PI * 2
  const radius = 7 + (hash(`${cluster}:r`) % 5000) / 1000
  return [Math.cos(angle) * radius, signed(cluster, 7) * 3.5, Math.sin(angle) * radius]
}

function focusedCluster(nodes: KairoGraphNode[], focusKey?: string | null): string | null {
  if (!focusKey) return null
  const focused = nodes.find((node) => graphNodeKey(node) === focusKey)
  return focused ? clusterForNode(focused) : null
}

function buildParticles(
  nodes: KairoGraphNode[],
  focusKey?: string | null,
  anchoredCluster?: string | null,
  initialPoses: Map<string, KairoGraphPose> = new Map(),
): Particle[] {
  const focusInitial = focusKey ? initialPoses.get(focusKey) : undefined

  return nodes.map((node) => {
    const key = graphNodeKey(node)
    const cluster = clusterForNode(node)
    const [cx, cy, cz] = clusterCenter(cluster, anchoredCluster)
    const pinned = key === focusKey
    const previous = initialPoses.get(key)
    const localSpread = cluster === anchoredCluster ? 3.25 : 4.2

    let x = cx + signed(key, 1) * localSpread
    let y = cy + signed(key, 2) * (cluster === anchoredCluster ? 2.6 : 3.4)
    let z = cz + signed(key, 3) * localSpread

    if (previous) {
      x = previous.x - (focusInitial?.x || 0)
      y = previous.y - (focusInitial?.y || 0)
      z = previous.z - (focusInitial?.z || 0)
    }

    return {
      key,
      x: pinned ? 0 : x,
      y: pinned ? 0 : y,
      z: pinned ? 0 : z,
      vx: 0,
      vy: 0,
      vz: 0,
      importance: node.importance,
      cluster,
      pinned,
    }
  })
}

function solve(request: LayoutRequest): LayoutResponse {
  const anchoredCluster = focusedCluster(request.nodes, request.focusKey)
  const initialPoses = new Map(request.initialPoses || [])
  const particles = buildParticles(
    request.nodes,
    request.focusKey,
    anchoredCluster,
    initialPoses,
  )
  const byKey = new Map(particles.map((particle) => [particle.key, particle]))
  const springs = request.edges
    .map((edge) => {
      const source = byKey.get(graphEntityKey(edge.source))
      const target = byKey.get(graphEntityKey(edge.target))
      return source && target ? { source, target, strength: edge.strength } : null
    })
    .filter((spring): spring is NonNullable<typeof spring> => spring !== null)

  const warmStart = request.warmStart === true
  const steps = warmStart
    ? (particles.length > 120 ? 70 : 96)
    : (particles.length > 120 ? 115 : 165)

  for (let step = 0; step < steps; step += 1) {
    const cooling = 1 - step / steps

    for (let index = 0; index < particles.length; index += 1) {
      const a = particles[index]
      for (let otherIndex = index + 1; otherIndex < particles.length; otherIndex += 1) {
        const b = particles[otherIndex]
        let dx = a.x - b.x
        let dy = a.y - b.y
        let dz = a.z - b.z
        let d2 = dx * dx + dy * dy + dz * dz
        if (d2 < 0.04) {
          dx += signed(`${a.key}:${b.key}`, 11) * 0.15
          dy += signed(`${a.key}:${b.key}`, 12) * 0.15
          dz += signed(`${a.key}:${b.key}`, 13) * 0.15
          d2 = dx * dx + dy * dy + dz * dz
        }
        const distance = Math.sqrt(d2)
        const clusterFactor = a.cluster === b.cluster ? 0.82 : 1.22
        const repel = (
          (0.18 + a.importance * 0.12 + b.importance * 0.12) * clusterFactor
        ) / Math.max(d2, 0.12)
        const fx = (dx / distance) * repel
        const fy = (dy / distance) * repel
        const fz = (dz / distance) * repel
        if (!a.pinned) {
          a.vx += fx
          a.vy += fy
          a.vz += fz
        }
        if (!b.pinned) {
          b.vx -= fx
          b.vy -= fy
          b.vz -= fz
        }
      }
    }

    for (const spring of springs) {
      const dx = spring.target.x - spring.source.x
      const dy = spring.target.y - spring.source.y
      const dz = spring.target.z - spring.source.z
      const distance = Math.max(0.001, Math.sqrt(dx * dx + dy * dy + dz * dz))
      const desired = 3.1 + (1 - spring.strength) * 2.6
      const tension = (distance - desired) * (0.008 + spring.strength * 0.012)
      const fx = (dx / distance) * tension
      const fy = (dy / distance) * tension
      const fz = (dz / distance) * tension
      if (!spring.source.pinned) {
        spring.source.vx += fx
        spring.source.vy += fy
        spring.source.vz += fz
      }
      if (!spring.target.pinned) {
        spring.target.vx -= fx
        spring.target.vy -= fy
        spring.target.vz -= fz
      }
    }

    for (const particle of particles) {
      if (particle.pinned) {
        particle.x = 0
        particle.y = 0
        particle.z = 0
        particle.vx = particle.vy = particle.vz = 0
        continue
      }

      const [cx, cy, cz] = clusterCenter(particle.cluster, anchoredCluster)
      const isFocusedCluster = Boolean(anchoredCluster && particle.cluster === anchoredCluster)
      const clusterPull = (isFocusedCluster ? 0.0052 : 0.0038) + cooling * 0.003
      particle.vx += (cx - particle.x) * clusterPull
      particle.vy += (cy - particle.y) * clusterPull
      particle.vz += (cz - particle.z) * clusterPull

      const distanceFromOrigin = Math.max(
        0.001,
        Math.sqrt(particle.x ** 2 + particle.y ** 2 + particle.z ** 2),
      )
      if (!request.focusKey && distanceFromOrigin < 3.4) {
        const push = (3.4 - distanceFromOrigin) * 0.025
        particle.vx += (particle.x / distanceFromOrigin) * push
        particle.vy += (particle.y / distanceFromOrigin) * push
        particle.vz += (particle.z / distanceFromOrigin) * push
      } else if (!isFocusedCluster) {
        particle.vx += -particle.x * 0.0009
        particle.vy += -particle.y * 0.0009
        particle.vz += -particle.z * 0.0009
      }

      const damping = 0.76 + cooling * 0.10
      particle.vx *= damping
      particle.vy *= damping
      particle.vz *= damping
      particle.x += particle.vx
      particle.y += particle.vy
      particle.z += particle.vz
    }
  }

  return {
    id: request.id,
    poses: particles.map((particle) => [
      particle.key,
      { x: particle.x, y: particle.y, z: particle.z },
    ]),
  }
}

self.onmessage = (event: MessageEvent<LayoutRequest>) => {
  self.postMessage(solve(event.data))
}

export {}
