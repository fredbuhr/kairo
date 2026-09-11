import { type FormEvent, useEffect, useState } from 'react'

import { readKnowledgeHttpError, readKnowledgeJson } from './knowledgeApi'
import type {
  AssetUpload,
  CanonicalDocument,
  DocumentImportRun,
} from './knowledgeTypes'
import { nevoliumFetch } from './lib/apiClient'

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

      const assetResponse = await nevoliumFetch(`${apiUrl}/v1/assets`, {
        method: 'POST',
        body: formData,
      })
      const asset = await readKnowledgeJson<AssetUpload>(assetResponse)

      const documentResponse = await nevoliumFetch(`${apiUrl}/v1/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_id: asset.id,
          title: selectedFile.name,
        }),
      })
      const run = await readKnowledgeJson<DocumentImportRun>(documentResponse)

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
      const response = await nevoliumFetch(
        `${apiUrl}/v1/documents/${selectedDocument.id}/reingest`,
        { method: 'POST' },
      )
      const run = await readKnowledgeJson<DocumentImportRun>(response)
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
      const response = await nevoliumFetch(
        `${apiUrl}/v1/assets/${selectedDocument.asset_id}/content`,
      )
      if (!response.ok) {
        throw await readKnowledgeHttpError(
          response,
          `Impossible d’ouvrir la source (${response.status}).`,
        )
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
