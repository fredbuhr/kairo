import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { useGraphActivity } from './useGraphActivity'

export function LiveGraphBridge() {
  const queryClient = useQueryClient()
  const { lastEvent } = useGraphActivity()

  useEffect(() => {
    if (!lastEvent) return
    const timer = window.setTimeout(() => {
      void queryClient.invalidateQueries({ queryKey: ['kairo-graph'] })
    }, 280)
    return () => window.clearTimeout(timer)
  }, [lastEvent, queryClient])

  return null
}
