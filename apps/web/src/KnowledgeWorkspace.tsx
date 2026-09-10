import { useEffect, useMemo, useState } from 'react'

import {
  MAX_CHUNK_PREVIEW_ITEMS,
  type KnowledgeInspectionTarget,
  useKnowledgeChunkInspection,
} from './knowledgeChunkInspection'
import {
  type CanonicalDocument,
  type DocumentVersion,
  useKnowledgeDocumentActions,
} from './knowledgeDocumentActions'
import { useKnowledgeDocumentDataLoading } from './knowledgeDocumentDataLoading'
import { useKnowledgeIngestionTracking } from './knowledgeIngestionTracking'
import { useProjectSelection } from './lib/projectSelection'

export type { KnowledgeInspectionTarget } from './knowledgeChunkInspection'

type Props = {
  apiUrl: string
  selectedDocumentId: string
  onSelectedDocumentIdChange: (documentId: string) => void
  inspectionTarget: KnowledgeInspectionTarget | null
}

const MAX_CHUNK_PREVIEW_CHARS = 1200

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: 'en attente',
    queued: 'en file',
    processing: 'traitement',
    completed: 'terminé',
    ready: 'prêt',
    failed: 'échec',
  }
  return labels[status] || status
}

function formatDate(value?: string | null) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function chunkExcerpt(text: string) {
  const value = text.trim()
  if (value.length <= MAX_CHUNK_PREVIEW_CHARS) return value
  return `${value.slice(0, MAX_CHUNK_PREVIEW_CHARS - 1)}…`
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

      {error && <div className="error-panel">{error}</div>}

      {loading && !error && (
        <div className="progress-panel">
          <strong>Chargement de votre base documentaire KAIRO.</strong>
          <span>Les Documents sont fournis par le Core selon le propriétaire authentifié.</span>
        </div>
      )}

      {!loading && !error && !selectedProjectId && (
        <div className="progress-panel">
          <strong>Aucun projet sélectionné.</strong>
          <span>Sélectionnez un projet dans Projects ou Research pour afficher ses Documents.</span>
        </div>
      )}

      {!loading && !error && selectedProjectId && (
        <>
          <form className="news-form" onSubmit={importDocument}>
            <label className="query-field">
              <span>Importer un Document</span>
              <input
                type="file"
                onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
                disabled={importing}
              />
            </label>
            <div className="news-controls">
              <button type="submit" disabled={importing || !selectedFile}>
                {importing ? 'Import…' : 'Importer dans Knowledge'}
              </button>
            </div>
          </form>

          {importError && <div className="error-panel">{importError}</div>}
          {trackingError && <div className="error-panel">Suivi ingestion · {trackingError}</div>}
          {trackingDocumentId && !trackingError && (
            <div className="progress-panel">
              <strong>Ingestion canonique en cours.</strong>
              <span>Knowledge actualise automatiquement le Document et ses versions.</span>
            </div>
          )}

          <section className="sources" aria-label="Documents du projet sélectionné">
            <div className="sources-title">
              <strong>Documents du projet</strong>
              <span>{projectDocuments.length} élément(s)</span>
            </div>
            <div className="source-list">
              {projectDocuments.length === 0 && (
                <div className="source-card">
                  <span className="source-id">0</span>
                  <div>
                    <strong>Aucun Document canonique pour ce projet.</strong>
                    <small>Importez un fichier pour créer le premier Document canonique.</small>
                  </div>
                </div>
              )}

              {projectDocuments.map((document) => (
                <div className="source-card" key={document.id}>
                  <span className="source-id">{statusLabel(document.status)}</span>
                  <div>
                    <strong>{document.title}</strong>
                    <small>{document.media_type || 'Type de média inconnu'}</small>
                    <small>
                      {formatDate(document.created_at)
                        ? `Créé le ${formatDate(document.created_at)}`
                        : 'Date de création indisponible'}
                      {formatDate(document.updated_at)
                        ? ` · mis à jour le ${formatDate(document.updated_at)}`
                        : ''}
                    </small>
                    {document.source_sha256 && (
                      <small>Source SHA-256 · {document.source_sha256.slice(0, 16)}…</small>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {projectDocuments.length > 0 && (
            <>
              <div className="news-controls">
                <label>
                  <span>Document sélectionné</span>
                  <select
                    value={selectedDocument?.id || ''}
                    onChange={(event) => onSelectedDocumentIdChange(event.target.value)}
                  >
                    {projectDocuments.map((document) => (
                      <option key={document.id} value={document.id}>
                        {document.title} · {statusLabel(document.status)}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() => void openSelectedSource()}
                  disabled={openingSource || !selectedDocument}
                >
                  {openingSource ? 'Ouverture…' : 'Ouvrir la source'}
                </button>
                <button
                  type="button"
                  onClick={() => void reingestSelectedDocument()}
                  disabled={
                    reingesting ||
                    Boolean(trackingDocumentId) ||
                    !selectedDocument ||
                    ['pending', 'processing'].includes(selectedDocument.status)
                  }
                >
                  {reingesting ? 'Reingest…' : 'Reingérer le Document'}
                </button>
              </div>

              {sourceError && <div className="error-panel">{sourceError}</div>}
              {reingestError && <div className="error-panel">{reingestError}</div>}

              {selectedDocument && (
                <article className="briefing" aria-label="Détail du Document sélectionné">
                  <div className="briefing-topline">
                    <div>
                      <span className="eyebrow">DOCUMENT SÉLECTIONNÉ</span>
                      <h3>{selectedDocument.title}</h3>
                    </div>
                    <span className={`run-state run-state-${selectedDocument.status}`}>
                      {statusLabel(selectedDocument.status)}
                    </span>
                  </div>
                  <div className="brief-summary">
                    {selectedDocument.media_type || 'Type de média inconnu'}
                  </div>
                </article>
              )}

              {versionError && <div className="error-panel">{versionError}</div>}

              {loadingVersions && !versionError && (
                <div className="progress-panel">
                  <strong>Chargement des versions canoniques.</strong>
                  <span>Le contenu des chunks n’est pas chargé automatiquement.</span>
                </div>
              )}

              {!loadingVersions && !versionError && selectedDocument && (
                <section className="sources" aria-label="Versions du Document sélectionné">
                  <div className="sources-title">
                    <strong>Versions canoniques</strong>
                    <span>{versions.length} version(s)</span>
                  </div>
                  <div className="source-list">
                    {versions.length === 0 && (
                      <div className="source-card">
                        <span className="source-id">0</span>
                        <div>
                          <strong>Aucune version disponible.</strong>
                          <small>Le Document ne possède pas encore de projection canonique.</small>
                        </div>
                      </div>
                    )}

                    {versions.map((version) => (
                      <div className="source-card" key={version.id}>
                        <span className="source-id">v{version.generation}</span>
                        <div>
                          <strong>
                            {version.parser}
                            {version.parser_version ? ` ${version.parser_version}` : ''}
                            {' · '}
                            {statusLabel(version.status)}
                          </strong>
                          <small>{version.chunk_count} chunk(s) canonique(s)</small>
                          <small>
                            {formatDate(version.created_at)
                              ? `Créée le ${formatDate(version.created_at)}`
                              : 'Date de création indisponible'}
                            {formatDate(version.completed_at)
                              ? ` · terminée le ${formatDate(version.completed_at)}`
                              : ''}
                          </small>
                          {version.source_sha256 && (
                            <small>Source SHA-256 · {version.source_sha256.slice(0, 16)}…</small>
                          )}
                          {version.last_error && <small>Erreur · {version.last_error}</small>}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {versions.length > 0 && (
                <>
                  <div className="news-controls">
                    <label>
                      <span>Version sélectionnée</span>
                      <select
                        value={selectedVersion?.id || ''}
                        onChange={(event) => setSelectedVersionId(event.target.value)}
                      >
                        {versions.map((version) => (
                          <option key={version.id} value={version.id}>
                            v{version.generation} · {version.parser} · {statusLabel(version.status)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      onClick={() => void loadChunkPage(0)}
                      disabled={loadingChunks || !selectedVersion}
                    >
                      {loadingChunks ? 'Chargement…' : 'Charger l’aperçu des chunks'}
                    </button>
                  </div>

                  {chunkError && <div className="error-panel">{chunkError}</div>}

                  {selectedVersion && !chunksLoaded && !loadingChunks && !chunkError && (
                    <div className="progress-panel">
                      <strong>Chunks non chargés.</strong>
                      <span>
                        Sélectionnez la version puis chargez explicitement un aperçu read-only.
                      </span>
                    </div>
                  )}

                  {chunksLoaded && !chunkError && selectedVersion && (
                    <>
                      <div className="news-controls" aria-label="Pagination des chunks">
                        <button
                          type="button"
                          onClick={() =>
                            void loadChunkPage(chunkOffset - MAX_CHUNK_PREVIEW_ITEMS)
                          }
                          disabled={loadingChunks || !canPreviousChunkPage}
                        >
                          ← Page précédente
                        </button>
                        <span className="route-chip">
                          {chunkPageStart === 0
                            ? `0 chunk sur ${selectedVersion.chunk_count}`
                            : `Chunks ${chunkPageStart}–${chunkPageEnd} sur ${selectedVersion.chunk_count}`}
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            void loadChunkPage(chunkOffset + MAX_CHUNK_PREVIEW_ITEMS)
                          }
                          disabled={loadingChunks || !canNextChunkPage}
                        >
                          Page suivante →
                        </button>
                      </div>

                      <section
                        className="sources"
                        aria-label="Aperçu des chunks de la version sélectionnée"
                      >
                        <div className="sources-title">
                          <strong>Aperçu des chunks · v{selectedVersion.generation}</strong>
                          <span>{chunkPreview.length} chunk(s) sur cette page</span>
                        </div>
                        <div className="source-list">
                          {chunkPreview.length === 0 && (
                            <div className="source-card">
                              <span className="source-id">0</span>
                              <div>
                                <strong>Aucun chunk disponible.</strong>
                                <small>
                                  Cette version ne contient aucun contenu canonique inspectable.
                                </small>
                              </div>
                            </div>
                          )}

                          {chunkPreview.map((chunk) => (
                            <div
                              className="source-card"
                              id={`knowledge-chunk-${chunk.id}`}
                              key={chunk.id}
                            >
                              <span className="source-id">#{chunk.ordinal}</span>
                              <div>
                                <strong>
                                  {chunk.id === focusedChunkId
                                    ? `Chunk canonique ${chunk.ordinal} · résultat sélectionné`
                                    : `Chunk canonique ${chunk.ordinal}`}
                                </strong>
                                <small>{chunkExcerpt(chunk.text)}</small>
                                <small>
                                  {formatDate(chunk.created_at)
                                    ? `Créé le ${formatDate(chunk.created_at)}`
                                    : 'Date de création indisponible'}
                                  {' · '}
                                  SHA-256 {chunk.content_sha256.slice(0, 16)}…
                                </small>
                              </div>
                            </div>
                          ))}
                        </div>
                      </section>
                    </>
                  )}
                </>
              )}
            </>
          )}
        </>
      )}
    </section>
  )
}
