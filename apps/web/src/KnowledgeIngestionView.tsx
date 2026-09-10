import type { FormEvent } from 'react'

type Props = {
  selectedFile: File | null
  importing: boolean
  importError: string | null
  trackingDocumentId: string | null
  trackingError: string | null
  onSelectFile: (file: File | null) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

export default function KnowledgeIngestionView({
  selectedFile,
  importing,
  importError,
  trackingDocumentId,
  trackingError,
  onSelectFile,
  onSubmit,
}: Props) {
  return (
    <>
      <form className="news-form" onSubmit={onSubmit}>
        <label className="query-field">
          <span>Importer un Document</span>
          <input
            type="file"
            onChange={(event) => onSelectFile(event.target.files?.[0] || null)}
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
    </>
  )
}
