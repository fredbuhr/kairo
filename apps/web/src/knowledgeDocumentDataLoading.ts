import { type Dispatch, type SetStateAction, useEffect } from 'react'

import type { CanonicalDocument, DocumentVersion } from './knowledgeDocumentActions'
import { kairoFetch } from './lib/apiClient'

type Options = {
  apiUrl: string
  documentId: string | null
  setDocuments: Dispatch<SetStateAction<CanonicalDocument[]>>
  setVersions: Dispatch<SetStateAction<DocumentVersion[]>>
  setVersionsDocumentId: Dispatch<SetStateAction<string | null>>
  setLoading: Dispatch<SetStateAction<boolean>>
  setLoadingVersions: Dispatch<SetStateAction<boolean>>
  setError: Dispatch<SetStateAction<string | null>>
  setVersionError: Dispatch<SetStateAction<string | null>>
}

async function readJson<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    const message = typeof detail === 'string' ? detail : detail?.message
    throw new Error(message || `KAIRO Core répond ${response.status}`)
  }
  return body as T
}

export function useKnowledgeDocumentDataLoading({
  apiUrl,
  documentId,
  setDocuments,
  setVersions,
  setVersionsDocumentId,
  setLoading,
  setLoadingVersions,
  setError,
  setVersionError,
}: Options) {
  useEffect(() => {
    let cancelled = false

    const loadDocuments = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await kairoFetch(`${apiUrl}/v1/documents`)
        const loadedDocuments = await readJson<CanonicalDocument[]>(response)
        if (!cancelled) setDocuments(loadedDocuments)
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : 'Impossible de charger les documents canoniques.',
          )
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadDocuments()
    return () => {
      cancelled = true
    }
  }, [apiUrl, setDocuments, setError, setLoading])

  useEffect(() => {
    let cancelled = false

    setVersions([])
    setVersionsDocumentId(null)
    setVersionError(null)
    if (!documentId) {
      setLoadingVersions(false)
      return () => {
        cancelled = true
      }
    }

    const loadVersions = async () => {
      setLoadingVersions(true)
      try {
        const response = await kairoFetch(`${apiUrl}/v1/documents/${documentId}/versions`)
        const loadedVersions = await readJson<DocumentVersion[]>(response)
        if (!cancelled) {
          setVersions(loadedVersions)
          setVersionsDocumentId(documentId)
        }
      } catch (loadError) {
        if (!cancelled) {
          setVersionError(
            loadError instanceof Error
              ? loadError.message
              : 'Impossible de charger les versions du Document.',
          )
        }
      } finally {
        if (!cancelled) setLoadingVersions(false)
      }
    }

    void loadVersions()
    return () => {
      cancelled = true
    }
  }, [
    apiUrl,
    documentId,
    setLoadingVersions,
    setVersionError,
    setVersions,
    setVersionsDocumentId,
  ])
}
