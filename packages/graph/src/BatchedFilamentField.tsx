import { useEffect, useMemo } from 'react'
import { useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js'
import { LineSegments2 } from 'three/examples/jsm/lines/LineSegments2.js'
import { LineSegmentsGeometry } from 'three/examples/jsm/lines/LineSegmentsGeometry.js'

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

type SegmentBatch = {
  positions: number[]
  colors: number[]
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
  if (highlighted) color.lerp(new THREE.Color('#d9fff7'), 0.48)
  const strength = 0.64 + edge.strength * 0.36
  color.multiplyScalar(dimmed ? 0.13 : strength)
  return color
}

function appendCurveSegments(
  batch: SegmentBatch,
  curve: THREE.CatmullRomCurve3,
  color: THREE.Color,
  sampleSegments: number,
) {
  let previous = curve.getPointAt(0)
  for (let step = 1; step <= sampleSegments; step += 1) {
    const current = curve.getPointAt(step / sampleSegments)
    batch.positions.push(
      previous.x,
      previous.y,
      previous.z,
      current.x,
      current.y,
      current.z,
    )
    batch.colors.push(color.r, color.g, color.b, color.r, color.g, color.b)
    previous = current
  }
}

function buildBatches({
  edges,
  poses,
  visibleKeys,
  emphasisKey,
  segments,
  strands,
}: BatchedFilamentFieldProps) {
  const base: SegmentBatch = { positions: [], colors: [] }
  const highlighted: SegmentBatch = { positions: [], colors: [] }
  const sampleSegments = Math.max(4, segments)
  const strandCount = Math.max(1, strands)

  for (const edge of edges) {
    const sourceKey = graphEntityKey(edge.source)
    const targetKey = graphEntityKey(edge.target)
    if (!visibleKeys.has(sourceKey) || !visibleKeys.has(targetKey)) continue

    const source = poses.get(sourceKey)
    const target = poses.get(targetKey)
    if (!source || !target) continue

    const isHighlighted = Boolean(
      emphasisKey && (sourceKey === emphasisKey || targetKey === emphasisKey),
    )
    const dimmed = Boolean(emphasisKey && !isHighlighted)
    const color = colorFor(edge, isHighlighted, dimmed)

    for (let strand = 0; strand < strandCount; strand += 1) {
      const curve = edgeCurve(edge, source, target, strand)
      appendCurveSegments(base, curve, color, sampleSegments)
      if (isHighlighted && strand === 0) {
        appendCurveSegments(highlighted, curve, color, sampleSegments)
      }
    }
  }

  return { base, highlighted }
}

function createGeometry(batch: SegmentBatch) {
  const geometry = new LineSegmentsGeometry()
  if (batch.positions.length > 0) {
    geometry.setPositions(batch.positions)
    geometry.setColors(batch.colors)
    geometry.computeBoundingSphere()
  }
  return geometry
}

function createLine(
  geometry: LineSegmentsGeometry,
  material: LineMaterial,
) {
  const line = new LineSegments2(geometry, material)
  line.computeLineDistances()
  line.frustumCulled = true
  return line
}

export function BatchedFilamentField(props: BatchedFilamentFieldProps) {
  const { size, gl } = useThree()
  const batches = useMemo(
    () => buildBatches(props),
    [
      props.edges,
      props.emphasisKey,
      props.poses,
      props.segments,
      props.strands,
      props.visibleKeys,
    ],
  )

  const baseGeometry = useMemo(() => createGeometry(batches.base), [batches.base])
  const highlightGeometry = useMemo(
    () => createGeometry(batches.highlighted),
    [batches.highlighted],
  )

  const coreMaterial = useMemo(() => new LineMaterial({
    color: 0xffffff,
    vertexColors: true,
    linewidth: 0.82,
    transparent: true,
    opacity: 0.62,
    depthWrite: false,
    toneMapped: false,
  }), [])
  const glowMaterial = useMemo(() => new LineMaterial({
    color: 0xffffff,
    vertexColors: true,
    linewidth: 2.35,
    transparent: true,
    opacity: 0.10,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    toneMapped: false,
  }), [])
  const highlightMaterial = useMemo(() => new LineMaterial({
    color: 0xffffff,
    vertexColors: true,
    linewidth: 1.55,
    transparent: true,
    opacity: 0.92,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    toneMapped: false,
  }), [])

  const coreLine = useMemo(
    () => createLine(baseGeometry, coreMaterial),
    [baseGeometry, coreMaterial],
  )
  const glowLine = useMemo(
    () => createLine(baseGeometry, glowMaterial),
    [baseGeometry, glowMaterial],
  )
  const highlightLine = useMemo(
    () => createLine(highlightGeometry, highlightMaterial),
    [highlightGeometry, highlightMaterial],
  )

  useEffect(() => {
    const pixelRatio = gl.getPixelRatio()
    const width = Math.max(1, size.width * pixelRatio)
    const height = Math.max(1, size.height * pixelRatio)
    coreMaterial.resolution.set(width, height)
    glowMaterial.resolution.set(width, height)
    highlightMaterial.resolution.set(width, height)
  }, [coreMaterial, glowMaterial, gl, highlightMaterial, size.height, size.width])

  useEffect(() => () => {
    baseGeometry.dispose()
    highlightGeometry.dispose()
  }, [baseGeometry, highlightGeometry])

  useEffect(() => () => {
    coreMaterial.dispose()
    glowMaterial.dispose()
    highlightMaterial.dispose()
  }, [coreMaterial, glowMaterial, highlightMaterial])

  if (batches.base.positions.length === 0) return null

  return (
    <group>
      <primitive object={glowLine} renderOrder={0} />
      <primitive object={coreLine} renderOrder={1} />
      {batches.highlighted.positions.length > 0 && (
        <primitive object={highlightLine} renderOrder={2} />
      )}
    </group>
  )
}
