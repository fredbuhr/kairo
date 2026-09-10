import { useEffect, useMemo, useState } from 'react'

import { kairoFetch } from './lib/apiClient'
import { useProjectSelection } from './lib/projectSelection'

type CanonicalDocument = {
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

type DocumentVersion = {
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

type DocumentChunk = {
  id: string
  document_version_id: string
  ordinal: number
  text: string
  content_sha256: string
  metadata_json: Record<string, unknown>
  created_at: string
}

type Props = {
  apiUrl: string
}

const MAX_CHUNK_PREVIEW_ITEMS = 20
const MAX_CHUNK_PREVIEW_CHARS = 1200

async function readJson<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    const message = typeof detail === 'string' ? detail : detail?.message
    throw new Error(message || `KAIRO Core répond ${response.status}`)
  }
  return body as T
}

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

export default function KnowledgeWorkspace({ apiUrl }: Props) {
  const { selectedProjectId } = useProjectSelection()
  const [documents, setDocuments] = useState<CanonicalDocument[]>([])
  const [selectedDocumentId, setSelectedDocumentId] = useState('')
  const [versions, setVersions] = useState<DocumentVersion[]>([])
  const [selectedVersionId, setSelectedVersionId] = useState('')
  const [chunks, setChunks] = useState<DocumentChunk[]>([])
  const [chunksLoaded, setChunksLoaded] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingVersions, setLoadingVersions] = useState(false)
  const [loadingChunks, setLoadingChunks] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [versionError, setVersionError] = useState<string | null>(null)
  const [chunkError, setChunkError] = useState<string | null>(null)

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
  }, [apiUrl])

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

  const selectedVersion = useMemo(
    () => versions.find((version) => version.id === selectedVersionId) || null,
    [versions, selectedVersionId],
  )

  const chunkPreview = useMemo(
    () => chunks.slice(0, MAX_CHUNK_PREVIEW_ITEMS),
    [chunks],
  )

  useEffect(() => {
    setSelectedDocumentId((current) => {
      if (current && projectDocuments.some((document) => document.id === current)) return current
      return projectDocuments[0]?.id || ''
    })
  }, [projectDocuments])

  useEffect(() => {
    let cancelled = false
    const documentId = selectedDocument?.id

    setVersions([])
    setSelectedVersionId('')
    setChunks([])
    setChunksLoaded(false)
    setChunkError(null)
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
        if (!cancelled) setVersions(loadedVersions)
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
  }, [apiUrl, selectedDocument?.id])

  useEffect(() => {
    setSelectedVersionId((current) => {
      if (current && versions.some((version) => version.id === current)) return current
      return versions[0]?.id || ''
    })
  }, [versions])

  useEffect(() => {
    setChunks([])
    setChunksLoaded(false)
    setChunkError(null)
  }, [selectedVersionId])

  async function loadChunkPreview() {
    if (!selectedVersion || loadingChunks) return

    setLoadingChunks(true)
    setChunkError(null)
    setChunksLoaded(false)
    try {
      const response = await kairoFetch(
        `${apiUrl}/v1/document-versions/${selectedVersion.id}/chunks`,
      )
      const loadedChunks = await readJson<DocumentChunk[]>(response)
      setChunks(loadedChunks)
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
                    <small>Knowledge est en lecture seule à cette étape.</small>
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
                    onChange={(event) => setSelectedDocumentId(event.target.value)}
                  >
                    {projectDocuments.map((document) => (
                      <option key={document.id} value={document.id}>
                        {document.title} · {statusLabel(document.status)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

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
                    <button type="button" onClick={loadChunkPreview} disabled={loadingChunks || !selectedVersion}>
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
                    <section className="sources" aria-label="Aperçu des chunks de la version sélectionnée">
                      <div className="sources-title">
                        <strong>Aperçu des chunks · v{selectedVersion.generation}</strong>
                        <span>
                          {chunkPreview.length} affiché(s) sur {chunks.length}
                          {chunks.length > MAX_CHUNK_PREVIEW_ITEMS
                            ? ` · limite UI ${MAX_CHUNK_PREVIEW_ITEMS}`
                            : ''}
                        </span>
                      </div>
                      <div className="source-list">
                        {chunkPreview.length === 0 && (
                          <div className="source-card">
                            <span className="source-id">0</span>
                            <div>
                              <strong>Aucun chunk disponible.</strong>
                              <small>Cette version ne contient aucun contenu canonique inspectable.</small>
                            </div>
                          </div>
                        )}

                        {chunkPreview.map((chunk) => (
                          <div className="source-card" key={chunk.id}>
                            <span className="source-id">#{chunk.ordinal}</span>
                            <div>
                              <strong>Chunk canonique {chunk.ordinal}</strong>
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
