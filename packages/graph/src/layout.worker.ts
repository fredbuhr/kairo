/// <reference lib="webworker" />

import type { KairoGraphEdge, KairoGraphNode, KairoGraphPose } from './types'
import { graphEntityKey, graphNodeKey } from './types'

type LayoutRequest = {
  id: number
  nodes: KairoGraphNode[]
  edges: KairoGraphEdge[]
  focusKey?: string | null
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
  for (let i = 0; i < value.length; i += 1) {
    h ^= value.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function signed(seed: string, salt: number): number {
  const value = hash(`${seed}:${salt}`) / 0xffffffff
  return value * 2 - 1
}

function clusterCenter(cluster: string): [number, number, number] {
  if (!cluster) return [0, 0, 0]
  const angle = ((hash(cluster) % 10000) / 10000) * Math.PI * 2
  const radius = 7 + (hash(`${cluster}:r`) % 5000) / 1000
  return [Math.cos(angle) * radius, signed(cluster, 7) * 3.5, Math.sin(angle) * radius]
}

function buildParticles(nodes: KairoGraphNode[], focusKey?: string | null): Particle[] {
  return nodes.map((node) => {
    const key = graphNodeKey(node)
    const cluster = node.cluster_hint || node.project_id || node.entity_type
    const [cx, cy, cz] = clusterCenter(cluster)
    const pinned = key === focusKey
    return {
      key,
      x: pinned ? 0 : cx + signed(key, 1) * 4.2,
      y: pinned ? 0 : cy + signed(key, 2) * 3.4,
      z: pinned ? 0 : cz + signed(key, 3) * 4.2,
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
  const particles = buildParticles(request.nodes, request.focusKey)
  const byKey = new Map(particles.map((particle) => [particle.key, particle]))
  const springs = request.edges
    .map((edge) => {
      const source = byKey.get(graphEntityKey(edge.source))
      const target = byKey.get(graphEntityKey(edge.target))
      return source && target ? { source, target, strength: edge.strength } : null
    })
    .filter((spring): spring is NonNullable<typeof spring> => spring !== null)

  const steps = particles.length > 120 ? 115 : 165
  for (let step = 0; step < steps; step += 1) {
    const cooling = 1 - step / steps

    for (let i = 0; i < particles.length; i += 1) {
      const a = particles[i]
      for (let j = i + 1; j < particles.length; j += 1) {
        const b = particles[j]
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
        const repel = (0.18 + a.importance * 0.12 + b.importance * 0.12) / Math.max(d2, 0.12)
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

      const [cx, cy, cz] = clusterCenter(particle.cluster)
      const clusterPull = 0.0038 + cooling * 0.003
      particle.vx += (cx - particle.x) * clusterPull
      particle.vy += (cy - particle.y) * clusterPull
      particle.vz += (cz - particle.z) * clusterPull

      const distanceFromOrigin = Math.max(0.001, Math.sqrt(particle.x ** 2 + particle.y ** 2 + particle.z ** 2))
      if (!request.focusKey && distanceFromOrigin < 3.4) {
        const push = (3.4 - distanceFromOrigin) * 0.025
        particle.vx += (particle.x / distanceFromOrigin) * push
        particle.vy += (particle.y / distanceFromOrigin) * push
        particle.vz += (particle.z / distanceFromOrigin) * push
      } else {
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
