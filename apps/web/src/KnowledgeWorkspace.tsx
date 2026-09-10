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

type Props = {
  apiUrl: string
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

export default function KnowledgeWorkspace({ apiUrl }: Props) {
  const { selectedProjectId } = useProjectSelection()
  const [documents, setDocuments] = useState<CanonicalDocument[]>([])
  const [selectedDocumentId, setSelectedDocumentId] = useState('')
  const [versions, setVersions] = useState<DocumentVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingVersions, setLoadingVersions] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [versionError, setVersionError] = useState<string | null>(null)

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
                  <span>Le contenu des chunks n’est pas chargé à cette étape.</span>
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
            </>
          )}
        </>
      )}
    </section>
  )
}
