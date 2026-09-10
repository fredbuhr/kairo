import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { readKnowledgeJson } from './knowledgeApi'
import type {
  CanonicalDocument,
  DocumentChunk,
  DocumentVersion,
  KnowledgeChunkWindow,
  KnowledgeInspectionTarget,
} from './knowledgeTypes'
import { kairoFetch } from './lib/apiClient'

type Options = {
  apiUrl: string
  selectedProjectId: string | null
  selectedDocument: CanonicalDocument | null
  selectedDocumentId: string
  inspectionTarget: KnowledgeInspectionTarget | null
  versions: DocumentVersion[]
  versionsDocumentId: string | null
  loading: boolean
  loadingVersions: boolean
}

export const MAX_CHUNK_PREVIEW_ITEMS = 20

export function useKnowledgeChunkInspection({
  apiUrl,
  selectedProjectId,
  selectedDocument,
  selectedDocumentId,
  inspectionTarget,
  versions,
  versionsDocumentId,
  loading,
  loadingVersions,
}: Options) {
  const handledInspectionTarget = useRef<KnowledgeInspectionTarget | null>(null)
  const [selectedVersionId, setSelectedVersionId] = useState('')
  const [chunks, setChunks] = useState<DocumentChunk[]>([])
  const [chunksLoaded, setChunksLoaded] = useState(false)
  const [chunkOffset, setChunkOffset] = useState(0)
  const [focusedChunkId, setFocusedChunkId] = useState<string | null>(null)
  const [loadingChunks, setLoadingChunks] = useState(false)
  const [chunkError, setChunkError] = useState<string | null>(null)

  const selectedVersion = useMemo(
    () => versions.find((version) => version.id === selectedVersionId) || null,
    [versions, selectedVersionId],
  )

  const chunkPreview = useMemo(
    () => chunks.slice(0, MAX_CHUNK_PREVIEW_ITEMS),
    [chunks],
  )

  const chunkPageStart = chunksLoaded && chunkPreview.length > 0 ? chunkOffset + 1 : 0
  const chunkPageEnd = chunksLoaded ? chunkOffset + chunkPreview.length : 0
  const canPreviousChunkPage = chunksLoaded && chunkOffset > 0
  const canNextChunkPage = Boolean(
    chunksLoaded && selectedVersion && chunkPageEnd < selectedVersion.chunk_count,
  )

  const resetChunks = useCallback(() => {
    setChunks([])
    setChunksLoaded(false)
    setChunkOffset(0)
    setFocusedChunkId(null)
    setChunkError(null)
  }, [])

  useEffect(() => {
    setSelectedVersionId('')
    resetChunks()
  }, [resetChunks, selectedDocument?.id])

  useEffect(() => {
    setSelectedVersionId((current) => {
      if (current && versions.some((version) => version.id === current)) return current
      return versions[0]?.id || ''
    })
  }, [versions])

  useEffect(() => {
    resetChunks()
  }, [resetChunks, selectedVersionId])

  useEffect(() => {
    if (!inspectionTarget || handledInspectionTarget.current === inspectionTarget) return
    if (loading || loadingVersions || !selectedProjectId) return
    if (inspectionTarget.documentId !== selectedDocumentId) return
    if (!selectedDocument || selectedDocument.id !== inspectionTarget.documentId) return
    if (versionsDocumentId !== selectedDocument.id) return

    const targetVersion = versions.find(
      (version) => version.id === inspectionTarget.documentVersionId,
    )
    if (!targetVersion) {
      handledInspectionTarget.current = inspectionTarget
      setChunkError('La Version associée à ce résultat de recherche est introuvable.')
      return
    }

    if (selectedVersionId !== targetVersion.id) {
      setSelectedVersionId(targetVersion.id)
      return
    }

    let cancelled = false

    const loadInspectionTarget = async () => {
      setLoadingChunks(true)
      setChunkError(null)
      setChunksLoaded(false)
      try {
        const params = new URLSearchParams({
          project_id: selectedProjectId,
          document_id: selectedDocument.id,
          version_id: targetVersion.id,
          chunk_id: inspectionTarget.chunkId,
          limit: String(MAX_CHUNK_PREVIEW_ITEMS),
        })
        const response = await kairoFetch(
          `${apiUrl}/v1/knowledge/chunk-window?${params.toString()}`,
        )
        const window = await readKnowledgeJson<KnowledgeChunkWindow>(response)
        if (cancelled) return

        setChunks(window.chunks)
        setChunkOffset(window.offset)
        setChunksLoaded(true)
        setFocusedChunkId(window.anchor_chunk_id)
        handledInspectionTarget.current = inspectionTarget
      } catch (loadError) {
        if (!cancelled) {
          handledInspectionTarget.current = inspectionTarget
          setChunks([])
          setChunkError(
            loadError instanceof Error
              ? loadError.message
              : `Impossible de charger le chunk #${inspectionTarget.ordinal}.`,
          )
        }
      } finally {
        if (!cancelled) setLoadingChunks(false)
      }
    }

    void loadInspectionTarget()
    return () => {
      cancelled = true
    }
  }, [
    apiUrl,
    inspectionTarget,
    loading,
    loadingVersions,
    selectedDocument,
    selectedDocumentId,
    selectedProjectId,
    selectedVersionId,
    versions,
    versionsDocumentId,
  ])

  useEffect(() => {
    if (!chunksLoaded || !focusedChunkId) return
    const frame = window.requestAnimationFrame(() => {
      document
        .getElementById(`knowledge-chunk-${focusedChunkId}`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [chunks, chunksLoaded, focusedChunkId])

  async function loadChunkPage(offset: number) {
    if (!selectedVersion || loadingChunks) return

    const maxOffset = Math.max(
      0,
      Math.floor(Math.max(0, selectedVersion.chunk_count - 1) / MAX_CHUNK_PREVIEW_ITEMS) *
        MAX_CHUNK_PREVIEW_ITEMS,
    )
    const normalizedOffset = Math.min(maxOffset, Math.max(0, offset))

    setLoadingChunks(true)
    setChunkError(null)
    setChunksLoaded(false)
    setFocusedChunkId(null)
    try {
      const response = await kairoFetch(
        `${apiUrl}/v1/document-versions/${selectedVersion.id}/chunks?offset=${normalizedOffset}&limit=${MAX_CHUNK_PREVIEW_ITEMS}`,
      )
      const loadedChunks = await readKnowledgeJson<DocumentChunk[]>(response)
      setChunks(loadedChunks)
      setChunkOffset(normalizedOffset)
      setChunksLoaded(true)
    } catch (loadError) {
      setChunks([])
      setChunkError(
        loadError instanceof Error ? loadError.message : 'Impossible de charger les chunks.',
      )
    } finally {
      setLoadingChunks(false)
    }
  }

  return {
    selectedVersionId,
    setSelectedVersionId,
    selectedVersion,
    chunkPreview,
    chunksLoaded,
    chunkOffset,
    focusedChunkId,
    loadingChunks,
    chunkError,
    chunkPageStart,
    chunkPageEnd,
    canPreviousChunkPage,
    canNextChunkPage,
    resetChunks,
    loadChunkPage,
  }
}
