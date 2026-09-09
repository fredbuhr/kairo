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
}

function buildClusters(
  nodes: KairoGraphNode[],
  poses: Map<string, KairoGraphPose>,
  visibleKeys: Set<string>,
): ClusterVisual[] {
  const groups = new Map<string, Array<{ node: KairoGraphNode; pose: KairoGraphPose }>>()

  for (const node of nodes) {
    const key = graphNodeKey(node)
    if (!visibleKeys.has(key)) continue
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
    for (const { node, pose } of values) {
      const weight = 0.65 + node.importance * 0.35
      center.addScaledVector(new THREE.Vector3(pose.x, pose.y, pose.z), weight)
      weightSum += weight
    }
    center.multiplyScalar(1 / Math.max(weightSum, 0.001))

    let radius = 1.4
    for (const { pose } of values) {
      radius = Math.max(
        radius,
        center.distanceTo(new THREE.Vector3(pose.x, pose.y, pose.z)) + 0.9,
      )
    }
    clusters.push({
      key,
      center,
      radius: Math.min(radius, 8.5),
      density: Math.min(1, values.length / 12),
    })
  }
  return clusters
}

export function ClusterField({
  nodes,
  poses,
  visibleKeys,
  detailLevel,
  reducedMotion,
}: ClusterFieldProps) {
  const mesh = useRef<THREE.InstancedMesh>(null)
  const dummy = useMemo(() => new THREE.Object3D(), [])
  const clusters = useMemo(
    () => buildClusters(nodes, poses, visibleKeys),
    [nodes, poses, visibleKeys],
  )
  const geometry = useMemo(() => new THREE.SphereGeometry(1, 18, 12), [])

  useEffect(() => () => geometry.dispose(), [geometry])

  useFrame(({ clock }) => {
    if (!mesh.current) return
    const visible = detailLevel <= 2 ? clusters : []
    for (let index = 0; index < visible.length; index += 1) {
      const cluster = visible[index]
      const breath = reducedMotion
        ? 1
        : 1 + Math.sin(clock.elapsedTime * 0.08 + index * 1.73) * 0.018
      dummy.position.copy(cluster.center)
      dummy.scale.setScalar(cluster.radius * breath)
      dummy.rotation.set(0, 0, 0)
      dummy.updateMatrix()
      mesh.current.setMatrixAt(index, dummy.matrix)
    }
    mesh.current.count = visible.length
    mesh.current.instanceMatrix.needsUpdate = true
  })

  if (clusters.length === 0 || detailLevel > 2) return null

  return (
    <instancedMesh
      ref={mesh}
      args={[geometry, undefined, Math.max(1, clusters.length)]}
      frustumCulled={false}
      raycast={() => null}
      renderOrder={-2}
    >
      <meshBasicMaterial
        color="#55cbc8"
        transparent
        opacity={detailLevel === 1 ? 0.017 : 0.010}
        depthWrite={false}
        side={THREE.BackSide}
        blending={THREE.AdditiveBlending}
        toneMapped={false}
      />
    </instancedMesh>
  )
}
