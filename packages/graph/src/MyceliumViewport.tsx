import { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

import { useGraphActivityKeys } from './activityStore'
import { BatchedFilamentField } from './BatchedFilamentField'
import { ClusterField } from './ClusterField'
import { InstancedNodeField } from './InstancedNodeField'
import type {
  KairoGraphEdge,
  KairoGraphNode,
  KairoGraphPose,
  KairoGraphProjection,
  KairoGraphQuality,
  KairoGraphTooltipPoint,
} from './types'
import { graphEntityKey, graphNodeKey } from './types'

export interface MyceliumViewportProps {
  projection: KairoGraphProjection | null
  selectedKey?: string | null
  activityKeys?: string[]
  quality?: KairoGraphQuality
  reducedMotion?: boolean
  className?: string
  onSelect?: (node: KairoGraphNode | null) => void
  onExplore?: (node: KairoGraphNode) => void
  onHover?: (node: KairoGraphNode | null, point: KairoGraphTooltipPoint | null) => void
}

type LayoutResponse = {
  id: number
  poses: Array<[string, KairoGraphPose]>
}

type QualitySettings = {
  dpr: number
  nodeSegments: number
  filamentSegments: number
  filamentStrands: number
  pulseLimit: number
  antialias: boolean
}

type SemanticBand = 1 | 2 | 3

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

function fallbackPose(node: KairoGraphNode, index: number, focusKey?: string | null): KairoGraphPose {
  const key = graphNodeKey(node)
  if (key === focusKey) return { x: 0, y: 0, z: 0 }
  const angle = ((hash(key) % 10000) / 10000) * Math.PI * 2
  const ring = 5 + (index % 6) * 1.25
  return {
    x: Math.cos(angle) * ring + signed(key, 1) * 1.6,
    y: signed(key, 2) * 5,
    z: Math.sin(angle) * ring + signed(key, 3) * 1.6,
  }
}

function qualitySettings(quality: KairoGraphQuality): QualitySettings {
  const hardwareConcurrency = typeof navigator !== 'undefined' ? navigator.hardwareConcurrency || 8 : 8
  const requested = quality === 'auto'
    ? (hardwareConcurrency <= 4 ? 'eco' : hardwareConcurrency <= 8 ? 'balanced' : 'high')
    : quality
  const deviceDpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1
  if (requested === 'eco') {
    return {
      dpr: 1,
      nodeSegments: 14,
      filamentSegments: 7,
      filamentStrands: 1,
      pulseLimit: 6,
      antialias: false,
    }
  }
  if (requested === 'balanced') {
    return {
      dpr: Math.min(deviceDpr, 1.35),
      nodeSegments: 18,
      filamentSegments: 10,
      filamentStrands: 2,
      pulseLimit: 14,
      antialias: true,
    }
  }
  return {
    dpr: Math.min(deviceDpr, 1.75),
    nodeSegments: 22,
    filamentSegments: 14,
    filamentStrands: 3,
    pulseLimit: 24,
    antialias: true,
  }
}

function semanticBandForDistance(distance: number): SemanticBand {
  if (distance > 18) return 1
  if (distance > 11) return 2
  return 3
}

function useGraphLayout(projection: KairoGraphProjection | null) {
  const [poses, setPoses] = useState<Map<string, KairoGraphPose>>(new Map())
  const requestId = useRef(0)

  useEffect(() => {
    if (!projection) {
      setPoses(new Map())
      return
    }

    const focusKey = projection.context.focus ? graphEntityKey(projection.context.focus) : null
    const immediate = new Map(
      projection.nodes.map((node, index) => [graphNodeKey(node), fallbackPose(node, index, focusKey)]),
    )
    setPoses(immediate)

    if (typeof Worker === 'undefined') return
    const id = ++requestId.current
    const worker = new Worker(new URL('./layout.worker.ts', import.meta.url), { type: 'module' })
    worker.onmessage = (event: MessageEvent<LayoutResponse>) => {
      if (event.data.id === id) setPoses(new Map(event.data.poses))
      worker.terminate()
    }
    worker.onerror = () => worker.terminate()
    worker.postMessage({
      id,
      nodes: projection.nodes,
      edges: projection.edges,
      focusKey,
    })
    return () => worker.terminate()
  }, [projection])

  return poses
}

function KairoAnchor({ reducedMotion }: { reducedMotion: boolean }) {
  const group = useRef<THREE.Group>(null)
  useFrame(({ clock }) => {
    if (!group.current || reducedMotion) return
    group.current.rotation.y = Math.sin(clock.elapsedTime * 0.08) * 0.16
    group.current.rotation.x = Math.cos(clock.elapsedTime * 0.06) * 0.08
    const scale = 1 + Math.sin(clock.elapsedTime * 0.55) * 0.025
    group.current.scale.setScalar(scale)
  })

  return (
    <group ref={group}>
      {[0, 1, 2, 3].map((index) => (
        <mesh key={index} rotation={[index * 0.57, index * 0.71, index * 0.38]}>
          <torusGeometry args={[1.05 + index * 0.045, 0.022, 8, 96]} />
          <meshBasicMaterial
            color={index % 2 ? '#75f0d2' : '#4be7ef'}
            transparent
            opacity={0.72}
          />
        </mesh>
      ))}
      <mesh>
        <sphereGeometry args={[0.24, 20, 20]} />
        <meshBasicMaterial color="#b8fff2" transparent opacity={0.18} />
      </mesh>
      <pointLight color="#3ce7e8" intensity={2.6} distance={8} decay={2} />
    </group>
  )
}

function CameraRig({ focusPose }: { focusPose?: KairoGraphPose | null }) {
  const { camera, gl } = useThree()
  const controls = useRef<OrbitControls | null>(null)
  const desiredTarget = useMemo(
    () => new THREE.Vector3(focusPose?.x || 0, focusPose?.y || 0, focusPose?.z || 0),
    [focusPose?.x, focusPose?.y, focusPose?.z],
  )

  useEffect(() => {
    const instance = new OrbitControls(camera, gl.domElement)
    instance.enableDamping = true
    instance.dampingFactor = 0.055
    instance.enablePan = true
    instance.panSpeed = 0.55
    instance.rotateSpeed = 0.34
    instance.zoomSpeed = 0.72
    instance.minDistance = 5.5
    instance.maxDistance = 42
    instance.minPolarAngle = Math.PI * 0.16
    instance.maxPolarAngle = Math.PI * 0.84
    instance.target.copy(desiredTarget)
    controls.current = instance
    return () => instance.dispose()
  }, [camera, desiredTarget, gl.domElement])

  useFrame(() => {
    const instance = controls.current
    if (!instance) return
    instance.target.lerp(desiredTarget, 0.075)
    instance.update()
  })

  return null
}

function edgeCurve(edge: KairoGraphEdge, source: KairoGraphPose, target: KairoGraphPose) {
  const start = new THREE.Vector3(source.x, source.y, source.z)
  const end = new THREE.Vector3(target.x, target.y, target.z)
  const midpoint = start.clone().add(end).multiplyScalar(0.5)
  const direction = end.clone().sub(start)
  const tangent = new THREE.Vector3(-direction.z, direction.x * 0.27, direction.x)
  if (tangent.lengthSq() < 0.0001) tangent.set(1, 0, 0)
  tangent.normalize()
  const curveOffset = (0.45 + direction.length() * 0.05) * signed(edge.id, 31)
  midpoint.add(tangent.multiplyScalar(curveOffset))
  midpoint.y += signed(edge.id, 32) * 0.48
  return new THREE.CatmullRomCurve3([start, midpoint, end], false, 'centripetal', 0.35)
}

function ActivityPulse({
  edge,
  source,
  target,
  index,
  reducedMotion,
}: {
  edge: KairoGraphEdge
  source: KairoGraphPose
  target: KairoGraphPose
  index: number
  reducedMotion: boolean
}) {
  const mesh = useRef<THREE.Mesh>(null)
  const curve = useMemo(() => edgeCurve(edge, source, target), [edge, source, target])
  const phase = ((hash(edge.id) % 1000) / 1000 + index * 0.17) % 1
  useFrame(({ clock }) => {
    if (!mesh.current) return
    const progress = reducedMotion
      ? phase
      : (phase + clock.elapsedTime * (0.055 + edge.strength * 0.035)) % 1
    const point = curve.getPointAt(progress)
    mesh.current.position.copy(point)
  })
  return (
    <mesh ref={mesh}>
      <sphereGeometry args={[0.05, 8, 8]} />
      <meshBasicMaterial color="#d4fff6" transparent opacity={0.82} depthWrite={false} />
    </mesh>
  )
}

function GraphScene({
  projection,
  poses,
  selectedKey,
  hoveredKey,
  activityKeys,
  settings,
  reducedMotion,
  onSelect,
  onExplore,
  onHover,
}: {
  projection: KairoGraphProjection
  poses: Map<string, KairoGraphPose>
  selectedKey?: string | null
  hoveredKey?: string | null
  activityKeys: string[]
  settings: QualitySettings
  reducedMotion: boolean
  onSelect?: (node: KairoGraphNode | null) => void
  onExplore?: (node: KairoGraphNode) => void
  onHover?: (node: KairoGraphNode | null, point: KairoGraphTooltipPoint | null) => void
}) {
  const { camera } = useThree()
  const focusKey = projection.context.focus ? graphEntityKey(projection.context.focus) : null
  const focusPose = focusKey ? poses.get(focusKey) : null
  const semanticTarget = useMemo(
    () => new THREE.Vector3(focusPose?.x || 0, focusPose?.y || 0, focusPose?.z || 0),
    [focusPose?.x, focusPose?.y, focusPose?.z],
  )
  const semanticBandRef = useRef<SemanticBand>(1)
  const [semanticBand, setSemanticBand] = useState<SemanticBand>(1)
  const nodeMap = useMemo(
    () => new Map(projection.nodes.map((node) => [graphNodeKey(node), node])),
    [projection.nodes],
  )
  const activityKeySet = useMemo(() => new Set(activityKeys), [activityKeys])
  const emphasisKey = selectedKey || hoveredKey || null

  useFrame(() => {
    const next = semanticBandForDistance(camera.position.distanceTo(semanticTarget))
    if (next !== semanticBandRef.current) {
      semanticBandRef.current = next
      setSemanticBand(next)
    }
  })

  const neighborKeys = useMemo(() => {
    const keys = new Set<string>()
    if (!emphasisKey) return keys
    keys.add(emphasisKey)
    for (const edge of projection.edges) {
      const sourceKey = graphEntityKey(edge.source)
      const targetKey = graphEntityKey(edge.target)
      if (sourceKey === emphasisKey) keys.add(targetKey)
      if (targetKey === emphasisKey) keys.add(sourceKey)
    }
    return keys
  }, [emphasisKey, projection.edges])

  const visibleKeys = useMemo(() => {
    const keys = new Set<string>()
    for (const node of projection.nodes) {
      const key = graphNodeKey(node)
      const forced = (
        key === focusKey
        || key === selectedKey
        || key === hoveredKey
        || neighborKeys.has(key)
        || activityKeySet.has(key)
      )
      if (forced || node.lod <= semanticBand) keys.add(key)
    }
    return keys
  }, [activityKeySet, focusKey, hoveredKey, neighborKeys, projection.nodes, selectedKey, semanticBand])

  const pulseEdges = useMemo(
    () => projection.edges
      .filter((edge) => {
        const sourceKey = graphEntityKey(edge.source)
        const targetKey = graphEntityKey(edge.target)
        if (!visibleKeys.has(sourceKey) || !visibleKeys.has(targetKey)) return false
        if (!activityKeySet.has(sourceKey) && !activityKeySet.has(targetKey)) return false
        if (emphasisKey && sourceKey !== emphasisKey && targetKey !== emphasisKey) return false
        const source = nodeMap.get(sourceKey)
        const target = nodeMap.get(targetKey)
        return Boolean(source && target)
      })
      .slice(0, settings.pulseLimit),
    [activityKeySet, emphasisKey, nodeMap, projection.edges, settings.pulseLimit, visibleKeys],
  )

  return (
    <>
      <color attach="background" args={['#02070b']} />
      <fog attach="fog" args={['#02070b', 16, 48]} />
      <ambientLight intensity={0.26} />
      <pointLight position={[8, 12, 10]} color="#58e7ef" intensity={8} distance={32} decay={2} />
      <pointLight position={[-10, -4, -12]} color="#65e9c6" intensity={5} distance={30} decay={2} />
      <CameraRig focusPose={focusPose} />

      {!focusKey && <KairoAnchor reducedMotion={reducedMotion} />}

      <ClusterField
        nodes={projection.nodes}
        poses={poses}
        visibleKeys={visibleKeys}
        detailLevel={semanticBand}
        reducedMotion={reducedMotion}
      />

      <BatchedFilamentField
        edges={projection.edges}
        poses={poses}
        visibleKeys={visibleKeys}
        emphasisKey={emphasisKey}
        segments={settings.filamentSegments}
        strands={settings.filamentStrands}
      />

      {pulseEdges.map((edge, index) => {
        const source = poses.get(graphEntityKey(edge.source))
        const target = poses.get(graphEntityKey(edge.target))
        if (!source || !target) return null
        return (
          <ActivityPulse
            key={`pulse:${edge.id}`}
            edge={edge}
            source={source}
            target={target}
            index={index}
            reducedMotion={reducedMotion}
          />
        )
      })}

      <InstancedNodeField
        nodes={projection.nodes}
        poses={poses}
        selectedKey={selectedKey}
        focusKey={focusKey}
        emphasisKey={emphasisKey}
        neighborKeys={neighborKeys}
        visibleKeys={visibleKeys}
        reducedMotion={reducedMotion}
        nodeSegments={settings.nodeSegments}
        onSelect={onSelect ? (node) => onSelect(node) : undefined}
        onExplore={onExplore}
        onHover={onHover}
      />
    </>
  )
}

export function MyceliumViewport({
  projection,
  selectedKey,
  activityKeys,
  quality = 'auto',
  reducedMotion = false,
  className,
  onSelect,
  onExplore,
  onHover,
}: MyceliumViewportProps) {
  const poses = useGraphLayout(projection)
  const bridgedActivityKeys = useGraphActivityKeys()
  const effectiveActivityKeys = activityKeys ?? bridgedActivityKeys
  const settings = useMemo(() => qualitySettings(quality), [quality])
  const [hoveredKey, setHoveredKey] = useState<string | null>(null)

  if (!projection) {
    return <div className={className} aria-label="Chargement du cerveau KAIRO" />
  }

  function handleHover(node: KairoGraphNode | null, point: KairoGraphTooltipPoint | null) {
    setHoveredKey(node ? graphNodeKey(node) : null)
    onHover?.(node, point)
  }

  return (
    <div className={className} role="application" aria-label="Cerveau spatial KAIRO">
      <Canvas
        camera={{ position: [0, 4.5, 20], fov: 50, near: 0.1, far: 90 }}
        dpr={settings.dpr}
        gl={{
          antialias: settings.antialias,
          alpha: false,
          powerPreference: quality === 'eco' ? 'low-power' : 'high-performance',
        }}
        onPointerMissed={() => onSelect?.(null)}
      >
        <GraphScene
          projection={projection}
          poses={poses}
          selectedKey={selectedKey}
          hoveredKey={hoveredKey}
          activityKeys={effectiveActivityKeys}
          settings={settings}
          reducedMotion={reducedMotion}
          onSelect={onSelect}
          onExplore={onExplore}
          onHover={handleHover}
        />
      </Canvas>
    </div>
  )
}
