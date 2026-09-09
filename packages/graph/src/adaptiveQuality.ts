import { useEffect, useRef, useState } from 'react'

import type { KairoGraphQuality } from './types'

export type KairoGraphResolvedQuality = Exclude<KairoGraphQuality, 'auto'>

function initialQuality(): KairoGraphResolvedQuality {
  if (typeof navigator === 'undefined') return 'balanced'
  const concurrency = navigator.hardwareConcurrency || 8
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory
  if (concurrency <= 4 || (memory !== undefined && memory <= 4)) return 'eco'
  if (concurrency <= 8 || (memory !== undefined && memory <= 8)) return 'balanced'
  return 'high'
}

function lowerQuality(value: KairoGraphResolvedQuality): KairoGraphResolvedQuality {
  if (value === 'high') return 'balanced'
  return 'eco'
}

function higherQuality(value: KairoGraphResolvedQuality): KairoGraphResolvedQuality {
  if (value === 'eco') return 'balanced'
  return 'high'
}

export function useAdaptiveGraphQuality(requested: KairoGraphQuality): KairoGraphResolvedQuality {
  const [resolved, setResolved] = useState<KairoGraphResolvedQuality>(() =>
    requested === 'auto' ? initialQuality() : requested,
  )
  const resolvedRef = useRef(resolved)

  useEffect(() => {
    if (requested !== 'auto') {
      resolvedRef.current = requested
      setResolved(requested)
      return
    }

    const initial = initialQuality()
    resolvedRef.current = initial
    setResolved(initial)

    let frame = 0
    let raf = 0
    let windowStartedAt = performance.now()
    let lowWindows = 0
    let highWindows = 0
    let ignoreUntil = performance.now() + 1800

    const commit = (next: KairoGraphResolvedQuality) => {
      if (next === resolvedRef.current) return
      resolvedRef.current = next
      setResolved(next)
      lowWindows = 0
      highWindows = 0
      // Ignore the transient cost of rebuilding geometry/DPR immediately after a tier change.
      ignoreUntil = performance.now() + 2200
    }

    const tick = (now: number) => {
      raf = requestAnimationFrame(tick)
      if (document.hidden) {
        frame = 0
        windowStartedAt = now
        lowWindows = 0
        highWindows = 0
        return
      }

      frame += 1
      const elapsed = now - windowStartedAt
      if (elapsed < 1600) return

      const fps = frame * 1000 / Math.max(elapsed, 1)
      frame = 0
      windowStartedAt = now
      if (now < ignoreUntil) return

      if (fps < 42) {
        lowWindows += 1
        highWindows = 0
      } else if (fps > 56) {
        highWindows += 1
        lowWindows = 0
      } else {
        lowWindows = Math.max(0, lowWindows - 1)
        highWindows = Math.max(0, highWindows - 1)
      }

      if (lowWindows >= 2 && resolvedRef.current !== 'eco') {
        commit(lowerQuality(resolvedRef.current))
        return
      }

      // Upgrades are deliberately slower than downgrades to avoid quality oscillation.
      if (highWindows >= 4 && resolvedRef.current !== 'high') {
        commit(higherQuality(resolvedRef.current))
      }
    }

    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [requested])

  return resolved
}
