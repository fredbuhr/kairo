import { useEffect, useMemo, useState } from 'react'

import { useKnowledgeChunkInspection } from './knowledgeChunkInspection'
import { useKnowledgeDocumentActions } from './knowledgeDocumentActions'
import { useKnowledgeDocumentDataLoading } from './knowledgeDocumentDataLoading'
import { useKnowledgeIngestionTracking } from './knowledgeIngestionTracking'
import KnowledgeIngestionView from './KnowledgeIngestionView'
import {
  KnowledgeChunksView,
  KnowledgeDocumentsView,
  KnowledgeVersionsView,
} from './KnowledgeInspectorView'
import KnowledgeWorkspaceStateView from './KnowledgeWorkspaceStateView'
import type {
  CanonicalDocument,
  DocumentVersion,
  KnowledgeInspectionTarget,
} from './knowledgeTypes'
import { useProjectSelection } from './lib/projectSelection'

type Props = {
  apiUrl: string
  selectedDocumentId: string
  onSelectedDocumentIdChange: (documentId: string) => void
  inspectionTarget: KnowledgeInspectionTarget | null
}

export default function KnowledgeWorkspace({
  apiUrl,
  selectedDocumentId,
  onSelectedDocumentIdChange,
  inspectionTarget,
}: Props) {
  const { selectedProjectId } = useProjectSelection()
  const [documents, setDocuments] = useState<CanonicalDocument[]>([])
  const [versions, setVersions] = useState<DocumentVersion[]>([])
  const [versionsDocumentId, setVersionsDocumentId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingVersions, setLoadingVersions] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [versionError, setVersionError] = useState<string | null>(null)

  const projectDocuments = useMemo(
    () =>
      selectedProjectId
        ? documents.filter((document) => document.project_id === selectedProjectId)
        : [],
    [documents, selectedProjectId],
  )

  const selectedDocument = useMemo(
    () => projectDocuments.find((document) => document.id === selectedDocumentId) || null,
    [projectDocuments, selectedDocumentId],
  )

  useKnowledgeDocumentDataLoading({
    apiUrl,
    documentId: selectedDocument?.id || null,
    setDocuments,
    setVersions,
    setVersionsDocumentId,
    setLoading,
    setLoadingVersions,
    setError,
    setVersionError,
  })

  const {
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
  } = useKnowledgeChunkInspection({
    apiUrl,
    selectedProjectId,
    selectedDocument,
    selectedDocumentId,
    inspectionTarget,
    versions,
    versionsDocumentId,
    loading,
    loadingVersions,
  })

  const {
    trackingDocumentId,
    setTrackingDocumentId,
    trackingError,
    resetTrackingError,
  } = useKnowledgeIngestionTracking({
    apiUrl,
    selectedDocumentId,
    setDocuments,
    setVersions,
    setVersionsDocumentId,
    setVersionError,
  })

  const {
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
  } = useKnowledgeDocumentActions({
    apiUrl,
    selectedProjectId,
    selectedDocument,
    trackingDocumentId,
    onTrackingReset: resetTrackingError,
    onImportComplete: (run) => {
      setDocuments((current) => [
        run.document,
        ...current.filter((document) => document.id !== run.document.id),
      ])
      onSelectedDocumentIdChange(run.document.id)
      setTrackingDocumentId(run.document.id)
    },
    onReingestBegin: resetChunks,
    onReingestComplete: (run) => {
      setDocuments((current) => [
        run.document,
        ...current.filter((document) => document.id !== run.document.id),
      ])
      setVersions((current) => [
        run.version,
        ...current.filter((version) => version.id !== run.version.id),
      ])
      setSelectedVersionId(run.version.id)
      setTrackingDocumentId(run.document.id)
    },
  })

  useEffect(() => {
    if (loading) return
    if (
      selectedDocumentId &&
      projectDocuments.some((document) => document.id === selectedDocumentId)
    ) {
      return
    }
    onSelectedDocumentIdChange(projectDocuments[0]?.id || '')
  }, [loading, onSelectedDocumentIdChange, projectDocuments, selectedDocumentId])

  return (
    <section className="news-workspace" aria-labelledby="knowledge-heading">
      <div className="news-heading">
        <div>
          <span className="eyebrow">KNOWLEDGE</span>
          <h2 id="knowledge-heading">Documents canoniques du projet actif.</h2>
        </div>
        <span className="run-state">{projectDocuments.length} document(s)</span>
      </div>

      <KnowledgeWorkspaceStateView
        loading={loading}
        error={error}
        selectedProjectId={selectedProjectId}
      />

      {!loading && !error && selectedProjectId && (
        <>
          <KnowledgeIngestionView
            selectedFile={selectedFile}
            importing={importing}
            importError={importError}
            trackingDocumentId={trackingDocumentId}
            trackingError={trackingError}
            onSelectFile={setSelectedFile}
            onSubmit={importDocument}
          />

          <KnowledgeDocumentsView
            documents={projectDocuments}
            selectedDocument={selectedDocument}
            trackingDocumentId={trackingDocumentId}
            openingSource={openingSource}
            reingesting={reingesting}
            sourceError={sourceError}
            reingestError={reingestError}
            onSelectDocument={onSelectedDocumentIdChange}
            onOpenSource={() => void openSelectedSource()}
            onReingest={() => void reingestSelectedDocument()}
          />

          {projectDocuments.length > 0 && (
            <>
              <KnowledgeVersionsView
                selectedDocument={selectedDocument}
                versions={versions}
                selectedVersion={selectedVersion}
                loadingVersions={loadingVersions}
                versionError={versionError}
                loadingChunks={loadingChunks}
                onSelectVersion={setSelectedVersionId}
                onLoadChunks={() => void loadChunkPage(0)}
              />

              {versions.length > 0 && (
                <KnowledgeChunksView
                  selectedVersion={selectedVersion}
                  chunks={chunkPreview}
                  chunksLoaded={chunksLoaded}
                  chunkOffset={chunkOffset}
                  focusedChunkId={focusedChunkId}
                  loadingChunks={loadingChunks}
                  chunkError={chunkError}
                  chunkPageStart={chunkPageStart}
                  chunkPageEnd={chunkPageEnd}
                  canPreviousChunkPage={canPreviousChunkPage}
                  canNextChunkPage={canNextChunkPage}
                  onLoadPage={(offset) => void loadChunkPage(offset)}
                />
              )}
            </>
          )}
        </>
      )}
    </section>
  )
}
