import { useEffect, useRef, useState } from 'react'
import { graphEntityKey, type KairoGraphActivityEvent } from '@kairo/graph'

import { API_URL } from '../../lib/api'

export type GraphActivityConnection = 'connecting' | 'live' | 'offline'

export function useGraphActivity(ttlMs = 4500) {
  const [connection, setConnection] = useState<GraphActivityConnection>('connecting')
  const [activeKeys, setActiveKeys] = useState<string[]>([])
  const [lastEvent, setLastEvent] = useState<KairoGraphActivityEvent | null>(null)
  const seen = useRef(new Set<string>())
  const timers = useRef(new Map<string, number>())

  useEffect(() => {
    const source = new EventSource(`${API_URL}/v1/graph/activity/stream`)

    function removeActiveKey(key: string) {
      timers.current.delete(key)
      setActiveKeys((current) => current.filter((value) => value !== key))
    }

    function activateKey(key: string) {
      const previousTimer = timers.current.get(key)
      if (previousTimer) window.clearTimeout(previousTimer)
      setActiveKeys((current) => current.includes(key) ? current : [...current, key])
      const timer = window.setTimeout(() => removeActiveKey(key), ttlMs)
      timers.current.set(key, timer)
    }

    source.onopen = () => setConnection('live')
    source.onerror = () => setConnection('offline')
    source.onmessage = (message) => {
      try {
        const activity = JSON.parse(message.data) as KairoGraphActivityEvent
        if (!activity?.id || seen.current.has(activity.id)) return
        seen.current.add(activity.id)
        if (seen.current.size > 500) {
          const values = Array.from(seen.current)
          seen.current = new Set(values.slice(values.length - 250))
        }

        activateKey(graphEntityKey(activity.entity))
        for (const related of activity.related || []) activateKey(graphEntityKey(related))
        setLastEvent(activity)
      } catch {
        // The stream is a progressive enhancement. Malformed activity must not break the Cockpit.
      }
    }

    return () => {
      source.close()
      for (const timer of timers.current.values()) window.clearTimeout(timer)
      timers.current.clear()
    }
  }, [ttlMs])

  return { connection, activeKeys, lastEvent }
}
