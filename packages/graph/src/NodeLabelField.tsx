import { useEffect, useMemo } from 'react'
import * as THREE from 'three'

import type { KairoGraphNode, KairoGraphPose } from './types'
import { graphNodeKey } from './types'

export interface NodeLabelFieldProps {
  nodes: KairoGraphNode[]
  poses: Map<string, KairoGraphPose>
  visibleKeys: Set<string>
  detailLevel: 1 | 2 | 3
  selectedKey?: string | null
}

type LabelEntry = {
  node: KairoGraphNode
  key: string
  pose: KairoGraphPose
}

function createLabelTexture(label: string): { texture: THREE.CanvasTexture; width: number } {
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')
  const scale = Math.max(1, Math.min(2, window.devicePixelRatio || 1))
  const fontSize = 18 * scale
  const paddingX = 16 * scale
  const paddingY = 9 * scale

  if (!context) {
    canvas.width = 2
    canvas.height = 2
    return { texture: new THREE.CanvasTexture(canvas), width: 1 }
  }

  context.font = `500 ${fontSize}px Inter, ui-sans-serif, system-ui, sans-serif`
  const measured = Math.min(300 * scale, Math.max(48 * scale, context.measureText(label).width))
  canvas.width = Math.ceil(measured + paddingX * 2)
  canvas.height = Math.ceil(fontSize + paddingY * 2)

  context.font = `500 ${fontSize}px Inter, ui-sans-serif, system-ui, sans-serif`
  context.textAlign = 'center'
  context.textBaseline = 'middle'
  context.fillStyle = 'rgba(230, 255, 251, 0.92)'
  context.shadowColor = 'rgba(56, 225, 218, 0.45)'
  context.shadowBlur = 7 * scale
  context.fillText(label, canvas.width / 2, canvas.height / 2)

  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.minFilter = THREE.LinearFilter
  texture.magFilter = THREE.LinearFilter
  texture.generateMipmaps = false
  texture.needsUpdate = true
  return { texture, width: canvas.width / Math.max(canvas.height, 1) }
}

function LabelSprite({ entry, selected }: { entry: LabelEntry; selected: boolean }) {
  const rendered = useMemo(() => createLabelTexture(entry.node.label), [entry.node.label])

  useEffect(() => () => rendered.texture.dispose(), [rendered.texture])

  const lift = 0.62 + entry.node.importance * 0.28
  const height = selected ? 0.62 : 0.50
  const width = Math.min(4.8, rendered.width * height)

  return (
    <sprite
      position={[entry.pose.x, entry.pose.y + lift, entry.pose.z]}
      scale={[width, height, 1]}
      renderOrder={4}
      raycast={() => null}
    >
      <spriteMaterial
        map={rendered.texture}
        transparent
        opacity={selected ? 1 : 0.84}
        depthWrite={false}
        depthTest
        toneMapped={false}
      />
    </sprite>
  )
}

export function NodeLabelField({
  nodes,
  poses,
  visibleKeys,
  detailLevel,
  selectedKey,
}: NodeLabelFieldProps) {
  const labels = useMemo(() => {
    const limit = detailLevel === 1 ? 7 : detailLevel === 2 ? 10 : 12
    return nodes
      .filter((node) => {
        const key = graphNodeKey(node)
        return visibleKeys.has(key) && poses.has(key) && (node.importance >= 0.56 || key === selectedKey)
      })
      .sort((a, b) => {
        const aKey = graphNodeKey(a)
        const bKey = graphNodeKey(b)
        if (aKey === selectedKey) return -1
        if (bKey === selectedKey) return 1
        return (b.importance + b.activity * 0.22) - (a.importance + a.activity * 0.22)
      })
      .slice(0, limit)
      .map((node) => ({ node, key: graphNodeKey(node), pose: poses.get(graphNodeKey(node))! }))
  }, [detailLevel, nodes, poses, selectedKey, visibleKeys])

  return (
    <group>
      {labels.map((entry) => (
        <LabelSprite key={entry.key} entry={entry} selected={entry.key === selectedKey} />
      ))}
    </group>
  )
}
