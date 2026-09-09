import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

import type { KairoGraphEdge, KairoGraphPose } from './types'
import { graphEntityKey } from './types'

export interface ActivityPulseFieldProps {
  edges: KairoGraphEdge[]
  poses: Map<string, KairoGraphPose>
  activeKeys: Set<string>
  visibleKeys: Set<string>
  emphasisKey?: string | null
  limit: number
  reducedMotion: boolean
}

type Pulse = {
  edge: KairoGraphEdge
  curve: THREE.CatmullRomCurve3
  phase: number
  speed: number
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

function edgeCurve(edge: KairoGraphEdge, source: KairoGraphPose, target: KairoGraphPose) {
  const start = new THREE.Vector3(source.x, source.y, source.z)
  const end = new THREE.Vector3(target.x, target.y, target.z)
  const midpoint = start.clone().add(end).multiplyScalar(0.5)
  const direction = end.clone().sub(start)
  const tangent = new THREE.Vector3(-direction.z, direction.x * 0.27, direction.x)
  if (tangent.lengthSq() < 0.0001) tangent.set(1, 0, 0)
  tangent.normalize()
  midpoint.add(tangent.multiplyScalar((0.45 + direction.length() * 0.05) * signed(edge.id, 31)))
  midpoint.y += signed(edge.id, 32) * 0.48
  return new THREE.CatmullRomCurve3([start, midpoint, end], false, 'centripetal', 0.35)
}

function buildPulses({
  edges,
  poses,
  activeKeys,
  visibleKeys,
  emphasisKey,
  limit,
}: Omit<ActivityPulseFieldProps, 'reducedMotion'>): Pulse[] {
  const pulses: Pulse[] = []
  for (const edge of edges) {
    const sourceKey = graphEntityKey(edge.source)
    const targetKey = graphEntityKey(edge.target)
    if (!visibleKeys.has(sourceKey) || !visibleKeys.has(targetKey)) continue
    if (!activeKeys.has(sourceKey) && !activeKeys.has(targetKey)) continue
    if (emphasisKey && sourceKey !== emphasisKey && targetKey !== emphasisKey) continue
    const source = poses.get(sourceKey)
    const target = poses.get(targetKey)
    if (!source || !target) continue
    pulses.push({
      edge,
      curve: edgeCurve(edge, source, target),
      phase: (hash(edge.id) % 1000) / 1000,
      speed: 0.055 + edge.strength * 0.035,
    })
    if (pulses.length >= limit) break
  }
  return pulses
}

export function ActivityPulseField(props: ActivityPulseFieldProps) {
  const mesh = useRef<THREE.InstancedMesh>(null)
  const dummy = useMemo(() => new THREE.Object3D(), [])
  const geometry = useMemo(() => new THREE.SphereGeometry(0.05, 8, 8), [])
  const pulses = useMemo(
    () => buildPulses(props),
    [
      props.activeKeys,
      props.edges,
      props.emphasisKey,
      props.limit,
      props.poses,
      props.visibleKeys,
    ],
  )

  useEffect(() => () => geometry.dispose(), [geometry])

  useFrame(({ clock }) => {
    if (!mesh.current) return
    for (let index = 0; index < pulses.length; index += 1) {
      const pulse = pulses[index]
      const progress = props.reducedMotion
        ? pulse.phase
        : (pulse.phase + clock.elapsedTime * pulse.speed) % 1
      dummy.position.copy(pulse.curve.getPointAt(progress))
      dummy.scale.setScalar(1)
      dummy.rotation.set(0, 0, 0)
      dummy.updateMatrix()
      mesh.current.setMatrixAt(index, dummy.matrix)
    }
    mesh.current.count = pulses.length
    mesh.current.instanceMatrix.needsUpdate = true
  })

  if (pulses.length === 0) return null

  return (
    <instancedMesh
      ref={mesh}
      args={[geometry, undefined, Math.max(1, pulses.length)]}
      frustumCulled={false}
      raycast={() => null}
      renderOrder={3}
    >
      <meshBasicMaterial
        color="#d4fff6"
        transparent
        opacity={0.84}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        toneMapped={false}
      />
    </instancedMesh>
  )
}
