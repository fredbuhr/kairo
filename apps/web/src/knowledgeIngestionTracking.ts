import { type Dispatch, type SetStateAction, useEffect, useState } from 'react'

import { readKnowledgeJson } from './knowledgeApi'
import type { CanonicalDocument, DocumentVersion } from './knowledgeTypes'
import { mergeById } from './lib/usePagedCollection'
import { kairoFetch } from './lib/apiClient'

type Options = {
  apiUrl: string
  selectedDocumentId: string
  setDocuments: Dispatch<SetStateAction<CanonicalDocument[]>>
  setVersions: Dispatch<SetStateAction<DocumentVersion[]>>
  setVersionsDocumentId: Dispatch<SetStateAction<string | null>>
  setVersionError: Dispatch<SetStateAction<string | null>>
}

export function useKnowledgeIngestionTracking({
  apiUrl,
  selectedDocumentId,
  setDocuments,
  setVersions,
  setVersionsDocumentId,
  setVersionError,
}: Options) {
  const [trackingDocumentId, setTrackingDocumentId] = useState<string | null>(null)
  const [trackingError, setTrackingError] = useState<string | null>(null)

  useEffect(() => {
    if (!trackingDocumentId) {
      setTrackingError(null)
      return
    }

    let cancelled = false
    let timer: number | undefined

    const pollIngestion = async () => {
      try {
        const documentResponse = await kairoFetch(`${apiUrl}/v1/documents/${trackingDocumentId}`)
        const document = await readKnowledgeJson<CanonicalDocument>(documentResponse)
        if (cancelled) return

        setDocuments((current) => [
          document,
          ...current.filter((item) => item.id !== document.id),
        ])
        setTrackingError(null)

        if (selectedDocumentId === document.id) {
          try {
            const versionsResponse = await kairoFetch(
              `${apiUrl}/v1/documents/${document.id}/versions`,
            )
            const loadedVersions = await readKnowledgeJson<DocumentVersion[]>(versionsResponse)
            if (!cancelled) {
              setVersions((current) => mergeById(current, loadedVersions).sort((a, b) => b.generation - a.generation))
              setVersionsDocumentId(document.id)
              setVersionError(null)
            }
          } catch (versionsLoadError) {
            if (!cancelled) {
              setVersionError(
                versionsLoadError instanceof Error
                  ? versionsLoadError.message
                  : 'Impossible d’actualiser les versions du Document.',
              )
            }
          }
        }

        if (document.status === 'ready' || document.status === 'failed') {
          setTrackingDocumentId(null)
          return
        }

        timer = window.setTimeout(pollIngestion, 1200)
      } catch (pollError) {
        if (!cancelled) {
          setTrackingError(
            pollError instanceof Error
              ? pollError.message
              : 'Impossible de suivre l’ingestion du Document.',
          )
          timer = window.setTimeout(pollIngestion, 2000)
        }
      }
    }

    void pollIngestion()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [
    apiUrl,
    selectedDocumentId,
    setDocuments,
    setVersionError,
    setVersions,
    setVersionsDocumentId,
    trackingDocumentId,
  ])

  return {
    trackingDocumentId,
    setTrackingDocumentId,
    trackingError,
    resetTrackingError: () => setTrackingError(null),
  }
}
