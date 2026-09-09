import { useMemo, useRef } from 'react'
import { useFrame, type ThreeEvent } from '@react-three/fiber'
import * as THREE from 'three'

import type { KairoGraphNode, KairoGraphPose, KairoGraphTooltipPoint } from './types'
import { graphNodeKey } from './types'

export interface InstancedNodeFieldProps {
  nodes: KairoGraphNode[]
  poses: Map<string, KairoGraphPose>
  selectedKey?: string | null
  focusKey?: string | null
  emphasisKey?: string | null
  neighborKeys: Set<string>
  visibleKeys: Set<string>
  reducedMotion: boolean
  nodeSegments: number
  onSelect?: (node: KairoGraphNode) => void
  onExplore?: (node: KairoGraphNode) => void
  onHover?: (node: KairoGraphNode | null, point: KairoGraphTooltipPoint | null) => void
}

function hash(value: string): number {
  let h = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    h ^= value.charCodeAt(index)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function nodeColor(node: KairoGraphNode): THREE.Color {
  const value = (() => {
    if (node.entity_type === 'approval') return '#b7f8d2'
    if (node.entity_type === 'project') return '#49e8ef'
    if (node.entity_type === 'task') return '#76f4cf'
    if (node.entity_type === 'document') return '#78cff8'
    if (node.entity_type === 'artifact') return '#8ce9d6'
    if (node.entity_type === 'conversation') return '#83d9ef'
    return '#65dce1'
  })()
  return new THREE.Color(value)
}

function radiusFor(node: KairoGraphNode) {
  return 0.22 + node.importance * 0.48
}

function pointerPoint(event: ThreeEvent<PointerEvent>): KairoGraphTooltipPoint {
  return { x: event.nativeEvent.clientX, y: event.nativeEvent.clientY }
}

export function InstancedNodeField({
  nodes,
  poses,
  selectedKey,
  focusKey,
  emphasisKey,
  neighborKeys,
  visibleKeys,
  reducedMotion,
  nodeSegments,
  onSelect,
  onExplore,
  onHover,
}: InstancedNodeFieldProps) {
  const mesh = useRef<THREE.InstancedMesh>(null)
  const halo = useRef<THREE.InstancedMesh>(null)
  const dummy = useMemo(() => new THREE.Object3D(), [])
  const workingColor = useMemo(() => new THREE.Color(), [])
  const birthTimes = useRef(new Map<string, number>())
  const visibleNodes = useMemo(
    () => nodes.filter((node) => visibleKeys.has(graphNodeKey(node)) && poses.has(graphNodeKey(node))),
    [nodes, poses, visibleKeys],
  )
  const geometry = useMemo(
    () => new THREE.SphereGeometry(1, nodeSegments, nodeSegments),
    [nodeSegments],
  )

  useFrame(({ clock }) => {
    if (!mesh.current || !halo.current) return
    const now = clock.elapsedTime

    for (let index = 0; index < visibleNodes.length; index += 1) {
      const node = visibleNodes[index]
      const key = graphNodeKey(node)
      const pose = poses.get(key)
      if (!pose) continue

      let bornAt = birthTimes.current.get(key)
      if (bornAt === undefined) {
        bornAt = now
        birthTimes.current.set(key, bornAt)
      }
      const age = Math.max(0, now - bornAt)
      const birthProgress = reducedMotion ? 1 : Math.min(1, age / 0.82)
      const emergence = 1 - (1 - birthProgress) ** 3
      const phase = ((hash(key) % 1000) / 1000) * Math.PI * 2
      const breathing = reducedMotion
        ? 1
        : 1 + Math.sin(now * 0.52 + phase) * (0.018 + node.activity * 0.018)
      const selected = key === selectedKey
      const focused = key === focusKey
      const emphasis = selected ? 1.18 : focused ? 1.11 : 1
      const radius = radiusFor(node)
      const floatY = reducedMotion ? 0 : Math.sin(now * 0.18 + phase) * 0.055
      const dimmed = Boolean(emphasisKey && !neighborKeys.has(key))

      dummy.position.set(pose.x, pose.y + floatY, pose.z)
      dummy.scale.setScalar(radius * emergence * breathing * emphasis)
      dummy.rotation.set(0, 0, 0)
      dummy.updateMatrix()
      mesh.current.setMatrixAt(index, dummy.matrix)

      dummy.scale.setScalar(radius * emergence * (selected ? 1.56 : 1.36))
      dummy.updateMatrix()
      halo.current.setMatrixAt(index, dummy.matrix)

      workingColor.copy(nodeColor(node))
      if (dimmed) workingColor.multiplyScalar(0.22)
      else if (selected) workingColor.multiplyScalar(1.18)
      mesh.current.setColorAt(index, workingColor)

      workingColor.copy(nodeColor(node))
      if (dimmed) workingColor.multiplyScalar(0.12)
      halo.current.setColorAt(index, workingColor)
    }

    mesh.current.count = visibleNodes.length
    halo.current.count = visibleNodes.length
    mesh.current.instanceMatrix.needsUpdate = true
    halo.current.instanceMatrix.needsUpdate = true
    if (mesh.current.instanceColor) mesh.current.instanceColor.needsUpdate = true
    if (halo.current.instanceColor) halo.current.instanceColor.needsUpdate = true
  })

  function nodeAt(event: ThreeEvent<PointerEvent>): KairoGraphNode | null {
    const index = event.instanceId
    return index === undefined ? null : visibleNodes[index] || null
  }

  return (
    <>
      <instancedMesh
        ref={mesh}
        args={[geometry, undefined, Math.max(1, visibleNodes.length)]}
        frustumCulled={false}
        onClick={(event) => {
          event.stopPropagation()
          const node = nodeAt(event)
          if (node) onSelect?.(node)
        }}
        onDoubleClick={(event) => {
          event.stopPropagation()
          const node = nodeAt(event)
          if (node) onExplore?.(node)
        }}
        onPointerOver={(event) => {
          event.stopPropagation()
          const node = nodeAt(event)
          if (!node) return
          document.body.style.cursor = 'pointer'
          onHover?.(node, pointerPoint(event))
        }}
        onPointerMove={(event) => {
          const node = nodeAt(event)
          if (node) onHover?.(node, pointerPoint(event))
        }}
        onPointerOut={() => {
          document.body.style.cursor = ''
          onHover?.(null, null)
        }}
      >
        <meshStandardMaterial
          vertexColors
          emissive="#2ab1b4"
          emissiveIntensity={0.68}
          roughness={0.34}
          metalness={0.08}
          transparent
          opacity={0.88}
        />
      </instancedMesh>

      <instancedMesh
        ref={halo}
        args={[geometry, undefined, Math.max(1, visibleNodes.length)]}
        frustumCulled={false}
        raycast={() => null}
      >
        <meshBasicMaterial vertexColors transparent opacity={0.065} depthWrite={false} />
      </instancedMesh>
    </>
  )
}
