import { useEffect, useMemo } from 'react'
import * as THREE from 'three'

import type { KairoGraphEdge, KairoGraphPose } from './types'
import { graphEntityKey } from './types'

export interface BatchedFilamentFieldProps {
  edges: KairoGraphEdge[]
  poses: Map<string, KairoGraphPose>
  visibleKeys: Set<string>
  emphasisKey?: string | null
  segments: number
  strands: number
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

function edgeCurve(
  edge: KairoGraphEdge,
  source: KairoGraphPose,
  target: KairoGraphPose,
  strand: number,
): THREE.CatmullRomCurve3 {
  const start = new THREE.Vector3(source.x, source.y, source.z)
  const end = new THREE.Vector3(target.x, target.y, target.z)
  const midpoint = start.clone().add(end).multiplyScalar(0.5)
  const direction = end.clone().sub(start)
  const tangent = new THREE.Vector3(-direction.z, direction.x * 0.27, direction.x)
  if (tangent.lengthSq() < 0.0001) tangent.set(1, 0, 0)
  tangent.normalize()

  const curveOffset = (0.44 + direction.length() * 0.047) * signed(edge.id, 31)
  midpoint.add(tangent.multiplyScalar(curveOffset))
  midpoint.y += signed(edge.id, 32) * 0.46

  if (strand > 0) {
    const strandOffset = 0.06 + strand * 0.028
    const secondary = new THREE.Vector3(direction.y, -direction.x, direction.z * 0.35)
    if (secondary.lengthSq() < 0.0001) secondary.set(0, 1, 0)
    secondary.normalize()
    midpoint.add(secondary.multiplyScalar(strandOffset * signed(edge.id, 60 + strand)))
  }

  return new THREE.CatmullRomCurve3([start, midpoint, end], false, 'centripetal', 0.35)
}

function colorFor(edge: KairoGraphEdge, highlighted: boolean, dimmed: boolean): THREE.Color {
  const color = new THREE.Color(
    edge.provenance === 'canonical_relationship' ? '#53e7e8' : '#78eecf',
  )
  if (highlighted) color.lerp(new THREE.Color('#d9fff7'), 0.42)
  const strength = 0.66 + edge.strength * 0.34
  color.multiplyScalar(dimmed ? 0.14 : strength)
  return color
}

function buildGeometry({
  edges,
  poses,
  visibleKeys,
  emphasisKey,
  segments,
  strands,
}: BatchedFilamentFieldProps): THREE.BufferGeometry {
  const positions: number[] = []
  const colors: number[] = []
  const sampleSegments = Math.max(4, segments)
  const strandCount = Math.max(1, strands)

  for (const edge of edges) {
    const sourceKey = graphEntityKey(edge.source)
    const targetKey = graphEntityKey(edge.target)
    if (!visibleKeys.has(sourceKey) || !visibleKeys.has(targetKey)) continue

    const source = poses.get(sourceKey)
    const target = poses.get(targetKey)
    if (!source || !target) continue

    const highlighted = Boolean(
      emphasisKey && (sourceKey === emphasisKey || targetKey === emphasisKey),
    )
    const dimmed = Boolean(emphasisKey && !highlighted)
    const color = colorFor(edge, highlighted, dimmed)

    for (let strand = 0; strand < strandCount; strand += 1) {
      const curve = edgeCurve(edge, source, target, strand)
      let previous = curve.getPointAt(0)
      for (let step = 1; step <= sampleSegments; step += 1) {
        const current = curve.getPointAt(step / sampleSegments)
        positions.push(
          previous.x,
          previous.y,
          previous.z,
          current.x,
          current.y,
          current.z,
        )
        colors.push(color.r, color.g, color.b, color.r, color.g, color.b)
        previous = current
      }
    }
  }

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
  if (positions.length > 0) geometry.computeBoundingSphere()
  return geometry
}

export function BatchedFilamentField(props: BatchedFilamentFieldProps) {
  const geometry = useMemo(
    () => buildGeometry(props),
    [
      props.edges,
      props.emphasisKey,
      props.poses,
      props.segments,
      props.strands,
      props.visibleKeys,
    ],
  )

  useEffect(() => () => geometry.dispose(), [geometry])

  return (
    <group>
      <lineSegments geometry={geometry} renderOrder={1}>
        <lineBasicMaterial
          vertexColors
          transparent
          opacity={0.58}
          depthWrite={false}
          toneMapped={false}
        />
      </lineSegments>
      <lineSegments geometry={geometry} renderOrder={0}>
        <lineBasicMaterial
          vertexColors
          transparent
          opacity={0.19}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
      </lineSegments>
    </group>
  )
}
