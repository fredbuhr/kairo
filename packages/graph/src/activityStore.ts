import { useSyncExternalStore } from 'react'

let snapshot: string[] = []
const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot() {
  return snapshot
}

export function publishGraphActivityKeys(keys: Iterable<string>) {
  const next = Array.from(new Set(keys)).sort()
  if (next.length === snapshot.length && next.every((value, index) => value === snapshot[index])) {
    return
  }
  snapshot = next
  for (const listener of listeners) listener()
}

export function useGraphActivityKeys() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}
