import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

import type { KairoGraphNode, KairoGraphPose } from './types'
import { graphNodeKey } from './types'

export interface ClusterFieldProps {
  nodes: KairoGraphNode[]
  poses: Map<string, KairoGraphPose>
  visibleKeys: Set<string>
  detailLevel: 1 | 2 | 3
  reducedMotion: boolean
}

type ClusterVisual = {
  key: string
  center: THREE.Vector3
  radius: number
  density: number
  activity: number
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
  return (hash(`${seed}:${salt}`) / 0xffffffff) * 2 - 1
}

function buildClusters(
  nodes: KairoGraphNode[],
  poses: Map<string, KairoGraphPose>,
): ClusterVisual[] {
  const groups = new Map<string, Array<{ node: KairoGraphNode; pose: KairoGraphPose }>>()

  for (const node of nodes) {
    const key = graphNodeKey(node)
    const pose = poses.get(key)
    if (!pose) continue
    const cluster = node.cluster_hint || node.project_id
    if (!cluster) continue
    const values = groups.get(cluster) || []
    values.push({ node, pose })
    groups.set(cluster, values)
  }

  const clusters: ClusterVisual[] = []
  for (const [key, values] of groups) {
    if (values.length < 3) continue

    const center = new THREE.Vector3()
    let weightSum = 0
    let activitySum = 0
    for (const { node, pose } of values) {
      const weight = 0.65 + node.importance * 0.35
      center.addScaledVector(new THREE.Vector3(pose.x, pose.y, pose.z), weight)
      weightSum += weight
      activitySum += node.activity
    }
    center.multiplyScalar(1 / Math.max(weightSum, 0.001))

    let radius = 1.4
    for (const { pose } of values) {
      radius = Math.max(
        radius,
        center.distanceTo(new THREE.Vector3(pose.x, pose.y, pose.z)) + 0.8,
      )
    }

    clusters.push({
      key,
      center,
      radius: Math.min(radius, 8.5),
      density: Math.min(1, values.length / 14),
      activity: Math.min(1, activitySum / Math.max(values.length, 1)),
    })
  }
  return clusters
}

function buildPointGeometry(clusters: ClusterVisual[], detailLevel: 1 | 2 | 3) {
  const positions: number[] = []
  const colors: number[] = []

  if (detailLevel > 2) {
    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.Float32BufferAttribute([], 3))
    geometry.setAttribute('color', new THREE.Float32BufferAttribute([], 3))
    return geometry
  }

  for (const cluster of clusters) {
    const pointCount = Math.round(
      (detailLevel === 1 ? 28 : 18) * (0.55 + cluster.density * 0.75),
    )
    const base = new THREE.Color('#57d6cf')
    const active = new THREE.Color('#8bf2d8')
    const color = base.lerp(active, cluster.activity * 0.32)

    for (let index = 0; index < pointCount; index += 1) {
      const seed = `${cluster.key}:${index}`
      const distance = Math.pow((hash(seed) % 10000) / 10000, 1.55) * cluster.radius
      const theta = ((hash(`${seed}:theta`) % 10000) / 10000) * Math.PI * 2
      const phi = Math.acos(Math.max(-1, Math.min(1, signed(seed, 17))))
      const flatten = 0.58 + Math.abs(signed(seed, 21)) * 0.34
      const x = cluster.center.x + Math.sin(phi) * Math.cos(theta) * distance
      const y = cluster.center.y + Math.cos(phi) * distance * flatten
      const z = cluster.center.z + Math.sin(phi) * Math.sin(theta) * distance
      positions.push(x, y, z)

      const brightness = 0.42 + Math.abs(signed(seed, 23)) * 0.48
      colors.push(color.r * brightness, color.g * brightness, color.b * brightness)
    }
  }

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
  if (positions.length > 0) geometry.computeBoundingSphere()
  return geometry
}

export function ClusterField({
  nodes,
  poses,
  visibleKeys,
  detailLevel,
  reducedMotion,
}: ClusterFieldProps) {
  const group = useRef<THREE.Group>(null)
  const clusters = useMemo(
    () => buildClusters(nodes, poses),
    [nodes, poses],
  )
  const geometry = useMemo(
    () => buildPointGeometry(clusters, detailLevel),
    [clusters, detailLevel],
  )
  const visibleClusterKeys = useMemo(() => {
    const keys = new Set<string>()
    for (const node of nodes) {
      const nodeKey = graphNodeKey(node)
      if (!visibleKeys.has(nodeKey)) continue
      const cluster = node.cluster_hint || node.project_id
      if (cluster) keys.add(cluster)
    }
    return keys
  }, [nodes, visibleKeys])
  const visibleRatio = clusters.length === 0
    ? 0
    : clusters.filter((cluster) => visibleClusterKeys.has(cluster.key)).length / clusters.length

  useEffect(() => () => geometry.dispose(), [geometry])

  useFrame(({ clock }) => {
    if (!group.current || reducedMotion) return
    group.current.rotation.y = Math.sin(clock.elapsedTime * 0.025) * 0.006
    group.current.rotation.x = Math.cos(clock.elapsedTime * 0.021) * 0.004
  })

  if (clusters.length === 0 || detailLevel > 2) return null

  return (
    <group ref={group} renderOrder={-2}>
      <points geometry={geometry} raycast={() => null}>
        <pointsMaterial
          vertexColors
          size={detailLevel === 1 ? 0.105 : 0.075}
          sizeAttenuation
          transparent
          opacity={(detailLevel === 1 ? 0.24 : 0.13) * (0.65 + visibleRatio * 0.35)}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
      </points>
    </group>
  )
}
