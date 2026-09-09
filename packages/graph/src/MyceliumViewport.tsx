import { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

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
  radialSegments: number
  pulseLimit: number
  antialias: boolean
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
  const requested = quality === 'auto' ? (hardwareConcurrency <= 4 ? 'eco' : hardwareConcurrency <= 8 ? 'balanced' : 'high') : quality
  const deviceDpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1
  if (requested === 'eco') {
    return { dpr: 1, nodeSegments: 16, filamentSegments: 10, radialSegments: 3, pulseLimit: 8, antialias: false }
  }
  if (requested === 'balanced') {
    return { dpr: Math.min(deviceDpr, 1.35), nodeSegments: 22, filamentSegments: 14, radialSegments: 4, pulseLimit: 18, antialias: true }
  }
  return { dpr: Math.min(deviceDpr, 1.75), nodeSegments: 28, filamentSegments: 18, radialSegments: 5, pulseLimit: 30, antialias: true }
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

function nodeColor(node: KairoGraphNode): string {
  if (node.entity_type === 'approval') return '#b7f8d2'
  if (node.entity_type === 'project') return '#49e8ef'
  if (node.entity_type === 'task') return '#76f4cf'
  if (node.entity_type === 'document') return '#78cff8'
  if (node.entity_type === 'artifact') return '#8ce9d6'
  if (node.entity_type === 'conversation') return '#83d9ef'
  return '#65dce1'
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
          <meshBasicMaterial color={index % 2 ? '#75f0d2' : '#4be7ef'} transparent opacity={0.72} />
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
    [focusPose],
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

function MyceliumNode({
  node,
  pose,
  selected,
  focused,
  reducedMotion,
  settings,
  onSelect,
  onExplore,
  onHover,
}: {
  node: KairoGraphNode
  pose: KairoGraphPose
  selected: boolean
  focused: boolean
  reducedMotion: boolean
  settings: QualitySettings
  onSelect?: (node: KairoGraphNode) => void
  onExplore?: (node: KairoGraphNode) => void
  onHover?: (node: KairoGraphNode | null, point: KairoGraphTooltipPoint | null) => void
}) {
  const mesh = useRef<THREE.Mesh>(null)
  const color = nodeColor(node)
  const baseRadius = 0.22 + node.importance * 0.48
  const key = graphNodeKey(node)
  const phase = ((hash(key) % 1000) / 1000) * Math.PI * 2

  useFrame(({ clock }) => {
    if (!mesh.current) return
    const breathing = reducedMotion ? 1 : 1 + Math.sin(clock.elapsedTime * 0.52 + phase) * (0.018 + node.activity * 0.018)
    const emphasis = selected ? 1.18 : focused ? 1.11 : 1
    mesh.current.scale.setScalar(breathing * emphasis)
    mesh.current.position.y = reducedMotion ? 0 : Math.sin(clock.elapsedTime * 0.18 + phase) * 0.055
  })

  function pointerPoint(event: ThreeEvent<PointerEvent>): KairoGraphTooltipPoint {
    return { x: event.nativeEvent.clientX, y: event.nativeEvent.clientY }
  }

  return (
    <group position={[pose.x, pose.y, pose.z]}>
      <mesh
        ref={mesh}
        onClick={(event) => {
          event.stopPropagation()
          onSelect?.(node)
        }}
        onDoubleClick={(event) => {
          event.stopPropagation()
          onExplore?.(node)
        }}
        onPointerOver={(event) => {
          event.stopPropagation()
          document.body.style.cursor = 'pointer'
          onHover?.(node, pointerPoint(event))
        }}
        onPointerMove={(event) => onHover?.(node, pointerPoint(event))}
        onPointerOut={() => {
          document.body.style.cursor = ''
          onHover?.(null, null)
        }}
      >
        <sphereGeometry args={[baseRadius, settings.nodeSegments, settings.nodeSegments]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={selected ? 1.55 : 0.82 + node.activity * 0.55}
          roughness={0.34}
          metalness={0.08}
          transparent
          opacity={0.74 + node.importance * 0.22}
        />
      </mesh>
      <mesh scale={selected ? 1.56 : 1.36}>
        <sphereGeometry args={[baseRadius, 12, 12]} />
        <meshBasicMaterial color={color} transparent opacity={selected ? 0.11 : 0.055} depthWrite={false} />
      </mesh>
    </group>
  )
}

function edgeCurve(edge: KairoGraphEdge, source: KairoGraphPose, target: KairoGraphPose) {
  const start = new THREE.Vector3(source.x, source.y, source.z)
  const end = new THREE.Vector3(target.x, target.y, target.z)
  const midpoint = start.clone().add(end).multiplyScalar(0.5)
  const direction = end.clone().sub(start)
  const tangent = new THREE.Vector3(-direction.z, direction.x * 0.27, direction.x).normalize()
  const curveOffset = (0.45 + direction.length() * 0.05) * signed(edge.id, 31)
  midpoint.add(tangent.multiplyScalar(curveOffset))
  midpoint.y += signed(edge.id, 32) * 0.48
  return new THREE.CatmullRomCurve3([start, midpoint, end], false, 'centripetal', 0.35)
}

function Filament({
  edge,
  source,
  target,
  settings,
  highlighted,
}: {
  edge: KairoGraphEdge
  source: KairoGraphPose
  target: KairoGraphPose
  settings: QualitySettings
  highlighted: boolean
}) {
  const curve = useMemo(() => edgeCurve(edge, source, target), [edge, source, target])
  const geometry = useMemo(
    () => new THREE.TubeGeometry(curve, settings.filamentSegments, 0.012 + edge.strength * 0.018, settings.radialSegments, false),
    [curve, edge.strength, settings.filamentSegments, settings.radialSegments],
  )
  useEffect(() => () => geometry.dispose(), [geometry])

  return (
    <mesh geometry={geometry}>
      <meshBasicMaterial
        color={edge.provenance === 'canonical_relationship' ? '#53e7e8' : '#78eecf'}
        transparent
        opacity={highlighted ? 0.74 : 0.18 + edge.strength * 0.22}
        depthWrite={false}
      />
    </mesh>
  )
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
    const progress = reducedMotion ? phase : (phase + clock.elapsedTime * (0.035 + edge.strength * 0.025)) % 1
    const point = curve.getPointAt(progress)
    mesh.current.position.copy(point)
  })
  return (
    <mesh ref={mesh}>
      <sphereGeometry args={[0.045, 8, 8]} />
      <meshBasicMaterial color="#c7fff3" transparent opacity={0.72} depthWrite={false} />
    </mesh>
  )
}

function GraphScene({
  projection,
  poses,
  selectedKey,
  settings,
  reducedMotion,
  onSelect,
  onExplore,
  onHover,
}: {
  projection: KairoGraphProjection
  poses: Map<string, KairoGraphPose>
  selectedKey?: string | null
  settings: QualitySettings
  reducedMotion: boolean
  onSelect?: (node: KairoGraphNode | null) => void
  onExplore?: (node: KairoGraphNode) => void
  onHover?: (node: KairoGraphNode | null, point: KairoGraphTooltipPoint | null) => void
}) {
  const focusKey = projection.context.focus ? graphEntityKey(projection.context.focus) : null
  const focusPose = focusKey ? poses.get(focusKey) : null
  const nodeMap = useMemo(() => new Map(projection.nodes.map((node) => [graphNodeKey(node), node])), [projection.nodes])
  const pulseEdges = useMemo(
    () => projection.edges
      .filter((edge) => {
        const source = nodeMap.get(graphEntityKey(edge.source))
        const target = nodeMap.get(graphEntityKey(edge.target))
        return source && target && source.activity + target.activity > 1.16
      })
      .slice(0, settings.pulseLimit),
    [nodeMap, projection.edges, settings.pulseLimit],
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

      {projection.edges.map((edge) => {
        const source = poses.get(graphEntityKey(edge.source))
        const target = poses.get(graphEntityKey(edge.target))
        if (!source || !target) return null
        const highlighted = Boolean(
          selectedKey && (graphEntityKey(edge.source) === selectedKey || graphEntityKey(edge.target) === selectedKey),
        )
        return <Filament key={edge.id} edge={edge} source={source} target={target} settings={settings} highlighted={highlighted} />
      })}

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

      {projection.nodes.map((node) => {
        const key = graphNodeKey(node)
        const pose = poses.get(key)
        if (!pose) return null
        return (
          <MyceliumNode
            key={key}
            node={node}
            pose={pose}
            selected={key === selectedKey}
            focused={key === focusKey}
            reducedMotion={reducedMotion}
            settings={settings}
            onSelect={onSelect ? (value) => onSelect(value) : undefined}
            onExplore={onExplore}
            onHover={onHover}
          />
        )
      })}
    </>
  )
}

export function MyceliumViewport({
  projection,
  selectedKey,
  quality = 'auto',
  reducedMotion = false,
  className,
  onSelect,
  onExplore,
  onHover,
}: MyceliumViewportProps) {
  const poses = useGraphLayout(projection)
  const settings = useMemo(() => qualitySettings(quality), [quality])

  if (!projection) {
    return <div className={className} aria-label="Chargement du cerveau KAIRO" />
  }

  return (
    <div className={className} role="application" aria-label="Cerveau spatial KAIRO">
      <Canvas
        camera={{ position: [0, 4.5, 20], fov: 50, near: 0.1, far: 90 }}
        dpr={settings.dpr}
        gl={{ antialias: settings.antialias, alpha: false, powerPreference: quality === 'eco' ? 'low-power' : 'high-performance' }}
        onPointerMissed={() => onSelect?.(null)}
      >
        <GraphScene
          projection={projection}
          poses={poses}
          selectedKey={selectedKey}
          settings={settings}
          reducedMotion={reducedMotion}
          onSelect={onSelect}
          onExplore={onExplore}
          onHover={onHover}
        />
      </Canvas>
    </div>
  )
}
