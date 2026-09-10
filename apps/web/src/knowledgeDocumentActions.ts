import { type FormEvent, useEffect, useState } from 'react'

import { kairoFetch } from './lib/apiClient'

export type CanonicalDocument = {
  id: string
  asset_id: string
  project_id: string
  title: string
  media_type?: string | null
  source_sha256?: string | null
  status: string
  metadata_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type DocumentVersion = {
  id: string
  document_id: string
  generation: number
  task_id?: string | null
  parser: string
  parser_version?: string | null
  source_sha256?: string | null
  status: string
  chunk_count: number
  metadata_json: Record<string, unknown>
  last_error?: string | null
  created_at: string
  completed_at?: string | null
}

type AssetUpload = {
  id: string
}

export type DocumentImportRun = {
  document: CanonicalDocument
  version: DocumentVersion
}

type Options = {
  apiUrl: string
  selectedProjectId: string | null
  selectedDocument: CanonicalDocument | null
  trackingDocumentId: string | null
  onTrackingReset: () => void
  onImportComplete: (run: DocumentImportRun) => void
  onReingestBegin: () => void
  onReingestComplete: (run: DocumentImportRun) => void
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

export function useKnowledgeDocumentActions({
  apiUrl,
  selectedProjectId,
  selectedDocument,
  trackingDocumentId,
  onTrackingReset,
  onImportComplete,
  onReingestBegin,
  onReingestComplete,
}: Options) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [reingesting, setReingesting] = useState(false)
  const [openingSource, setOpeningSource] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [reingestError, setReingestError] = useState<string | null>(null)
  const [sourceError, setSourceError] = useState<string | null>(null)

  useEffect(() => {
    setReingestError(null)
    setSourceError(null)
  }, [selectedDocument?.id])

  async function importDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedProjectId || !selectedFile || importing) return

    const formElement = event.currentTarget
    setImporting(true)
    setImportError(null)
    onTrackingReset()

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('project_id', selectedProjectId)

      const assetResponse = await kairoFetch(`${apiUrl}/v1/assets`, {
        method: 'POST',
        body: formData,
      })
      const asset = await readJson<AssetUpload>(assetResponse)

      const documentResponse = await kairoFetch(`${apiUrl}/v1/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_id: asset.id,
          title: selectedFile.name,
        }),
      })
      const run = await readJson<DocumentImportRun>(documentResponse)

      onImportComplete(run)
      setSelectedFile(null)
      formElement.reset()
    } catch (importFailure) {
      setImportError(
        importFailure instanceof Error
          ? importFailure.message
          : 'Impossible d’importer ce Document dans Knowledge.',
      )
    } finally {
      setImporting(false)
    }
  }

  async function reingestSelectedDocument() {
    if (!selectedDocument || reingesting || trackingDocumentId) return

    setReingesting(true)
    setReingestError(null)
    onTrackingReset()
    onReingestBegin()

    try {
      const response = await kairoFetch(
        `${apiUrl}/v1/documents/${selectedDocument.id}/reingest`,
        { method: 'POST' },
      )
      const run = await readJson<DocumentImportRun>(response)
      onReingestComplete(run)
    } catch (reingestFailure) {
      setReingestError(
        reingestFailure instanceof Error
          ? reingestFailure.message
          : 'Impossible de relancer l’ingestion du Document.',
      )
    } finally {
      setReingesting(false)
    }
  }

  async function openSelectedSource() {
    if (!selectedDocument || openingSource) return

    const previewWindow = window.open('', '_blank')
    if (!previewWindow) {
      setSourceError('Le navigateur a bloqué l’ouverture du fichier source.')
      return
    }
    previewWindow.opener = null

    setOpeningSource(true)
    setSourceError(null)
    try {
      const response = await kairoFetch(
        `${apiUrl}/v1/assets/${selectedDocument.asset_id}/content`,
      )
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        const detail = body?.detail
        const message = typeof detail === 'string' ? detail : detail?.message
        throw new Error(message || `Impossible d’ouvrir la source (${response.status}).`)
      }

      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      previewWindow.location.replace(objectUrl)
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 120_000)
    } catch (sourceFailure) {
      previewWindow.close()
      setSourceError(
        sourceFailure instanceof Error
          ? sourceFailure.message
          : 'Impossible d’ouvrir le fichier source.',
      )
    } finally {
      setOpeningSource(false)
    }
  }

  return {
    selectedFile,
    setSelectedFile,
    importing,
    reingesting,
    openingSource,
    importError,
    reingestError,
    sourceError,
    importDocument,
    reingestSelectedDocument,
    openSelectedSource,
  }
}
