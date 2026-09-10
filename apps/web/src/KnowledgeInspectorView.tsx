import { MAX_CHUNK_PREVIEW_ITEMS } from './knowledgeChunkInspection'
import type { CanonicalDocument, DocumentChunk, DocumentVersion } from './knowledgeTypes'

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

type DocumentsProps = {
  documents: CanonicalDocument[]
  selectedDocument: CanonicalDocument | null
  trackingDocumentId: string | null
  openingSource: boolean
  reingesting: boolean
  sourceError: string | null
  reingestError: string | null
  onSelectDocument: (documentId: string) => void
  onOpenSource: () => void
  onReingest: () => void
}

export function KnowledgeDocumentsView({
  documents,
  selectedDocument,
  trackingDocumentId,
  openingSource,
  reingesting,
  sourceError,
  reingestError,
  onSelectDocument,
  onOpenSource,
  onReingest,
}: DocumentsProps) {
  return (
    <>
      <section className="sources" aria-label="Documents du projet sélectionné">
        <div className="sources-title">
          <strong>Documents du projet</strong>
          <span>{documents.length} élément(s)</span>
        </div>
        <div className="source-list">
          {documents.length === 0 && (
            <div className="source-card">
              <span className="source-id">0</span>
              <div>
                <strong>Aucun Document canonique pour ce projet.</strong>
                <small>Importez un fichier pour créer le premier Document canonique.</small>
              </div>
            </div>
          )}

          {documents.map((document) => (
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

      {documents.length > 0 && (
        <>
          <div className="news-controls">
            <label>
              <span>Document sélectionné</span>
              <select
                value={selectedDocument?.id || ''}
                onChange={(event) => onSelectDocument(event.target.value)}
              >
                {documents.map((document) => (
                  <option key={document.id} value={document.id}>
                    {document.title} · {statusLabel(document.status)}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => onOpenSource()}
              disabled={openingSource || !selectedDocument}
            >
              {openingSource ? 'Ouverture…' : 'Ouvrir la source'}
            </button>
            <button
              type="button"
              onClick={() => onReingest()}
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
        </>
      )}
    </>
  )
}

type VersionsProps = {
  selectedDocument: CanonicalDocument | null
  versions: DocumentVersion[]
  selectedVersion: DocumentVersion | null
  loadingVersions: boolean
  versionError: string | null
  loadingChunks: boolean
  onSelectVersion: (versionId: string) => void
  onLoadChunks: () => void
}

export function KnowledgeVersionsView({
  selectedDocument,
  versions,
  selectedVersion,
  loadingVersions,
  versionError,
  loadingChunks,
  onSelectVersion,
  onLoadChunks,
}: VersionsProps) {
  return (
    <>
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
        <div className="news-controls">
          <label>
            <span>Version sélectionnée</span>
            <select
              value={selectedVersion?.id || ''}
              onChange={(event) => onSelectVersion(event.target.value)}
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
            onClick={() => onLoadChunks()}
            disabled={loadingChunks || !selectedVersion}
          >
            {loadingChunks ? 'Chargement…' : 'Charger l’aperçu des chunks'}
          </button>
        </div>
      )}
    </>
  )
}

type ChunksProps = {
  selectedVersion: DocumentVersion | null
  chunks: DocumentChunk[]
  chunksLoaded: boolean
  chunkOffset: number
  focusedChunkId: string | null
  loadingChunks: boolean
  chunkError: string | null
  chunkPageStart: number
  chunkPageEnd: number
  canPreviousChunkPage: boolean
  canNextChunkPage: boolean
  onLoadPage: (offset: number) => void
}

export function KnowledgeChunksView({
  selectedVersion,
  chunks,
  chunksLoaded,
  chunkOffset,
  focusedChunkId,
  loadingChunks,
  chunkError,
  chunkPageStart,
  chunkPageEnd,
  canPreviousChunkPage,
  canNextChunkPage,
  onLoadPage,
}: ChunksProps) {
  return (
    <>
      {chunkError && <div className="error-panel">{chunkError}</div>}

      {selectedVersion && !chunksLoaded && !loadingChunks && !chunkError && (
        <div className="progress-panel">
          <strong>Chunks non chargés.</strong>
          <span>Sélectionnez la version puis chargez explicitement un aperçu read-only.</span>
        </div>
      )}

      {chunksLoaded && !chunkError && selectedVersion && (
        <>
          <div className="news-controls" aria-label="Pagination des chunks">
            <button
              type="button"
              onClick={() => onLoadPage(chunkOffset - MAX_CHUNK_PREVIEW_ITEMS)}
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
              onClick={() => onLoadPage(chunkOffset + MAX_CHUNK_PREVIEW_ITEMS)}
              disabled={loadingChunks || !canNextChunkPage}
            >
              Page suivante →
            </button>
          </div>

          <section className="sources" aria-label="Aperçu des chunks de la version sélectionnée">
            <div className="sources-title">
              <strong>Aperçu des chunks · v{selectedVersion.generation}</strong>
              <span>{chunks.length} chunk(s) sur cette page</span>
            </div>
            <div className="source-list">
              {chunks.length === 0 && (
                <div className="source-card">
                  <span className="source-id">0</span>
                  <div>
                    <strong>Aucun chunk disponible.</strong>
                    <small>Cette version ne contient aucun contenu canonique inspectable.</small>
                  </div>
                </div>
              )}

              {chunks.map((chunk) => (
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
  )
}
