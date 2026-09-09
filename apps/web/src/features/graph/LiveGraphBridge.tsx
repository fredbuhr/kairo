import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { useGraphActivity } from './useGraphActivity'

export function LiveGraphBridge() {
  const queryClient = useQueryClient()
  const { lastEvent } = useGraphActivity()

  useEffect(() => {
    if (!lastEvent) return
    void queryClient.invalidateQueries({ queryKey: ['kairo-graph'] })
  }, [lastEvent, queryClient])

  return null
}
