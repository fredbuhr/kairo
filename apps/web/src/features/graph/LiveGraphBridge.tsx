import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { publishGraphActivityKeys } from '@kairo/graph'

import { useGraphActivity } from './useGraphActivity'

export function LiveGraphBridge() {
  const queryClient = useQueryClient()
  const { activeKeys, lastEvent } = useGraphActivity()

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

  useEffect(() => () => publishGraphActivityKeys([]), [])

  return null
}
