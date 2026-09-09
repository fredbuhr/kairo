import { useEffect, useRef, useState } from 'react'
import { graphEntityKey, type KairoGraphActivityEvent } from '@kairo/graph'

import { API_URL } from '../../lib/api'
import { authenticatedFetch } from '../../lib/authSession'

export type GraphActivityConnection = 'connecting' | 'live' | 'offline'

function eventData(block: string) {
  const chunks: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('data:')) chunks.push(line.slice(5).trimStart())
  }
  return chunks.join('\n')
}

export function useGraphActivity(ttlMs = 4500) {
  const [connection, setConnection] = useState<GraphActivityConnection>('connecting')
  const [activeKeys, setActiveKeys] = useState<string[]>([])
  const [lastEvent, setLastEvent] = useState<KairoGraphActivityEvent | null>(null)
  const seen = useRef(new Set<string>())
  const timers = useRef(new Map<string, number>())

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    let reconnectTimer: number | undefined
    let reconnectAttempt = 0

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

    function acceptMessage(data: string) {
      if (!data) return
      try {
        const activity = JSON.parse(data) as KairoGraphActivityEvent
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

    function scheduleReconnect() {
      if (cancelled) return
      setConnection('offline')
      const delay = Math.min(15_000, 700 * 2 ** Math.min(reconnectAttempt, 4))
      reconnectAttempt += 1
      reconnectTimer = window.setTimeout(() => void connect(), delay)
    }

    async function connect() {
      if (cancelled) return
      setConnection(reconnectAttempt === 0 ? 'connecting' : 'offline')
      try {
        const response = await authenticatedFetch(`${API_URL}/v1/graph/activity/stream`, {
          headers: { Accept: 'text/event-stream' },
          cache: 'no-store',
          signal: controller.signal,
        })
        if (!response.ok) throw new Error(`Graph activity stream returned ${response.status}`)
        if (!response.body) throw new Error('Graph activity stream has no readable body')

        reconnectAttempt = 0
        setConnection('live')
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (!cancelled) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true }).replaceAll('\r\n', '\n')
          let boundary = buffer.indexOf('\n\n')
          while (boundary >= 0) {
            const block = buffer.slice(0, boundary)
            buffer = buffer.slice(boundary + 2)
            acceptMessage(eventData(block))
            boundary = buffer.indexOf('\n\n')
          }
        }

        if (!cancelled) scheduleReconnect()
      } catch (error) {
        if (cancelled || controller.signal.aborted) return
        scheduleReconnect()
      }
    }

    void connect()

    return () => {
      cancelled = true
      controller.abort()
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
      for (const timer of timers.current.values()) window.clearTimeout(timer)
      timers.current.clear()
    }
  }, [ttlMs])

  return { connection, activeKeys, lastEvent }
}
