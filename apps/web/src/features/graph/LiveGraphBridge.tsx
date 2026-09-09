import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { publishGraphActivityKeys } from '@kairo/graph'

import {
  desktopAttentionNotificationsEnabled,
  isKairoDesktopRuntime,
  sendDesktopNotification,
} from '../../lib/desktopBridge'
import { useGraphActivity } from './useGraphActivity'

const ATTENTION_EVENT_TYPES = new Set([
  'approval.requested',
  'execution.completed',
  'execution.failed',
  'automation.invocation.completed',
  'automation.invocation.failed',
  'finance.connector.sync.completed',
  'finance.connector.sync.failed',
  'document.ingestion.completed',
  'document.ingestion.failed',
  'research.completed',
  'research.failed',
])

function notificationFor(eventType: string) {
  if (eventType === 'approval.requested') {
    return { title: 'KAIRO · Approbation requise', body: 'Une action attend votre décision dans KAIRO.' }
  }
  if (eventType.endsWith('.failed')) {
    return { title: 'KAIRO · Action en échec', body: eventType.replaceAll('.', ' · ') }
  }
  return { title: 'KAIRO · Action terminée', body: eventType.replaceAll('.', ' · ') }
}

export function LiveGraphBridge() {
  const queryClient = useQueryClient()
  const { activeKeys, lastEvent } = useGraphActivity()
  const notifiedEvents = useRef(new Set<string>())

  useEffect(() => {
    publishGraphActivityKeys(activeKeys)
  }, [activeKeys])

  useEffect(() => {
    if (!lastEvent) return
    const timer = window.setTimeout(() => {
      void queryClient.invalidateQueries({ queryKey: ['kairo-graph'] })
    }, 280)
    return () => window.clearTimeout(timer)
  }, [lastEvent, queryClient])

  useEffect(() => {
    if (!lastEvent || !isKairoDesktopRuntime() || !desktopAttentionNotificationsEnabled()) return
    if (!ATTENTION_EVENT_TYPES.has(lastEvent.event_type)) return
    if (document.visibilityState === 'visible' && document.hasFocus()) return
    if (notifiedEvents.current.has(lastEvent.id)) return

    notifiedEvents.current.add(lastEvent.id)
    if (notifiedEvents.current.size > 200) {
      const recent = Array.from(notifiedEvents.current).slice(-100)
      notifiedEvents.current = new Set(recent)
    }

    const notification = notificationFor(lastEvent.event_type)
    void sendDesktopNotification(notification.title, notification.body).catch(() => {
      // Native notifications are an optional progressive enhancement. Permission refusal or OS
      // delivery failure must never break realtime graph updates or the Cockpit itself.
    })
  }, [lastEvent])

  useEffect(() => () => publishGraphActivityKeys([]), [])

  return null
}
