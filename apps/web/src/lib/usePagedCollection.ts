import { useCallback, useEffect, useRef, useState } from 'react'

import { nevoliumFetch } from './apiClient'

export function mergeById<T extends { id: string }>(current: T[], incoming: T[]): T[] {
  const rows = new Map(current.map((item) => [item.id, item]))
  for (const item of incoming) rows.set(item.id, item)
  return [...rows.values()]
}

/** Read one page per user action, cancel stale scopes, and preserve an explicitly selected item. */
export function usePagedCollection<T extends { id: string }>(url: string | null, pinnedUrl?: string | null) {
  const [items, setItems] = useState<T[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pinned = useRef<T | null>(null)
  const activeUrl = useRef<string | null>(null)
  const activePin = useRef<string | null | undefined>(null)
  const scope = useRef(0)
  const busy = useRef(false)
  const request = useRef<AbortController | null>(null)

  const readPage = useCallback(async (next: string | null, append: boolean, generation: number) => {
    if (!url || busy.current) return
    busy.current = true
    setLoading(true)
    setError(null)
    const controller = new AbortController()
    request.current = controller
    try {
      const response = await nevoliumFetch(url + (next ? `${url.includes('?') ? '&' : '?'}cursor=${encodeURIComponent(next)}` : ''), { signal: controller.signal })
      const rows = await response.json()
      if (!response.ok) throw new Error(typeof rows?.detail === 'string' ? rows.detail : `Nevolium Core répond ${response.status}`)
      if (!Array.isArray(rows)) throw new Error('Réponse de pagination invalide.')
      if (generation !== scope.current || controller.signal.aborted) return
      setItems((current) => append ? mergeById(current, rows as T[]) : mergeById(rows as T[], pinned.current ? [pinned.current] : []))
      setCursor(response.headers.get('X-Nevolium-Next-Cursor') || null)
    } catch (cause) {
      if (generation === scope.current && !controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Chargement impossible.')
    } finally {
      if (generation === scope.current) {
        busy.current = false
        setLoading(false)
      }
    }
  }, [url])

  useEffect(() => {
    activeUrl.current = url
    const generation = ++scope.current
    busy.current = false
    setItems([])
    setCursor(null)
    setError(null)
    setLoading(Boolean(url))
    void readPage(null, false, generation)
    return () => { ++scope.current; request.current?.abort() }
  }, [url, readPage])

  // A selected object can be older than the first page; fetching it never scans preceding pages.
  const [pinLoading, setPinLoading] = useState(false)
  const [pinError, setPinError] = useState<string | null>(null)
  useEffect(() => {
    activePin.current = pinnedUrl
    pinned.current = null
    if (!url || !pinnedUrl) { setPinLoading(false); setPinError(null); return }
    const controller = new AbortController()
    setPinLoading(true)
    setPinError(null)
    void (async () => {
      try {
        const response = await nevoliumFetch(pinnedUrl, { signal: controller.signal })
        if (response.status === 404) return
        if (!response.ok) throw new Error(`Nevolium Core répond ${response.status}`)
        const row = await response.json() as T
        if (!controller.signal.aborted) { pinned.current = row; setItems((current) => mergeById(current, [row])) }
      } catch (cause) {
        if (!controller.signal.aborted) setPinError(cause instanceof Error ? cause.message : 'Sélection indisponible.')
      } finally {
        if (!controller.signal.aborted) setPinLoading(false)
      }
    })()
    return () => controller.abort()
  }, [url, pinnedUrl])

  const sameScope = activeUrl.current === url
  return { items: sameScope ? items : [], setItems, loading: loading || pinLoading || !sameScope || Boolean(url && pinnedUrl && activePin.current !== pinnedUrl), error: sameScope ? error || pinError : null, hasMore: sameScope && Boolean(cursor),
    loadMore: () => cursor ? readPage(cursor, true, scope.current) : Promise.resolve(), reload: () => readPage(null, false, scope.current) }
}
