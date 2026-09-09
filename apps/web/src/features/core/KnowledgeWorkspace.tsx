import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { KairoGraphEntityRef } from '@kairo/graph'

import {
  createDocument,
  fetchDocumentChunks,
  fetchDocuments,
  fetchDocumentVersions,
  reingestDocument,
  searchKnowledge,
  uploadAsset,
  type DocumentRecord,
  type DocumentVersionRecord,
  type ProjectRecord,
} from '../../lib/api'

function shortDate(value?: string | null) {
  if (!value) return '—'
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }).format(new Date(value))
  } catch {
    return value
  }
}

function documentStatus(value: string) {
  const labels: Record<string, string> = {
    pending: 'En attente',
    processing: 'Indexation…',
    ready: 'Prêt',
    failed: 'Échec',
  }
  return labels[value] || value
}

function mediaLabel(value?: string | null) {
  if (!value) return 'Document'
  if (value.includes('pdf')) return 'PDF'
  if (value.includes('word')) return 'Word'
  if (value.includes('markdown')) return 'Markdown'
  if (value.startsWith('text/')) return 'Texte'
  return value.split('/').pop()?.toUpperCase() || 'Document'
}

function latestCompleted(versions: DocumentVersionRecord[]) {
  return versions.find((version) => version.status === 'completed') || versions[0] || null
}

function UploadDocument({ projects, onUploaded }: {
  projects: ProjectRecord[]
  onUploaded: (document: DocumentRecord) => void
}) {
  const client = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [projectId, setProjectId] = useState('')
  const [inputKey, setInputKey] = useState(0)
  const mutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('Choisissez un fichier à importer.')
      const asset = await uploadAsset(file, projectId || null)
      return createDocument(asset.id, title.trim() || file.name)
    },
    onSuccess: async (run) => {
      setFile(null)
      setTitle('')
      setInputKey((value) => value + 1)
      onUploaded(run.document)
      await Promise.all([
        client.invalidateQueries({ queryKey: ['documents'] }),
        client.invalidateQueries({ queryKey: ['tasks'] }),
        client.invalidateQueries({ queryKey: ['kairo-graph'] }),
      ])
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!file || mutation.isPending) return
    mutation.mutate()
  }

  return (
    <form className="knowledge-import" onSubmit={submit}>
      <div className="workspace-create-heading">
        <div><span className="kairo-kicker">IMPORTER</span><strong>Nourrir KAIRO</strong></div>
        <button type="submit" disabled={!file || mutation.isPending}>
          {mutation.isPending ? 'Import…' : 'Importer'}
        </button>
      </div>
      <label className="knowledge-file-input">
        <input
          key={inputKey}
          type="file"
          onChange={(event) => setFile(event.target.files?.[0] || null)}
        />
        <span>{file ? file.name : 'Choisir un document'}</span>
        <small>{file ? `${Math.max(1, Math.round(file.size / 1024))} Ko` : 'PDF, texte, documents bureautiques…'}</small>
      </label>
      <input
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        placeholder="Titre KAIRO (optionnel)"
        maxLength={320}
      />
      <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
        <option value="">Bibliothèque générale</option>
        {projects.map((project) => (
          <option key={project.id} value={project.id}>{project.name}</option>
        ))}
      </select>
      <p>Le fichier devient un Asset canonique puis un Document versionné. Docling l’indexe durablement sans créer de copie métier parallèle dans l’interface.</p>
      {mutation.isError && (
        <small className="workspace-error">
          {mutation.error instanceof Error ? mutation.error.message : 'Import impossible.'}
        </small>
      )}
    </form>
  )
}

export function KnowledgeWorkspace({
  projects,
  onExploreEntity,
}: {
  projects: ProjectRecord[]
  onExploreEntity: (entity: KairoGraphEntityRef) => void
}) {
  const client = useQueryClient()
  const documentsQuery = useQuery({
    queryKey: ['documents'],
    queryFn: fetchDocuments,
    staleTime: 6000,
    refetchInterval: (query) => query.state.data?.some((document) => ['pending', 'processing'].includes(document.status)) ? 2200 : false,
  })
  const documents = documentsQuery.data || []
  const projectById = useMemo(
    () => new Map(projects.map((project) => [project.id, project])),
    [projects],
  )
  const [selectedDocumentId, setSelectedDocumentId] = useState('')
  const [selectedVersionId, setSelectedVersionId] = useState('')
  const [queryInput, setQueryInput] = useState('')
  const [committedQuery, setCommittedQuery] = useState('')

  useEffect(() => {
    if (documents.length === 0) {
      setSelectedDocumentId('')
      return
    }
    if (!documents.some((document) => document.id === selectedDocumentId)) {
      setSelectedDocumentId(documents[0].id)
    }
  }, [documents, selectedDocumentId])

  const selectedDocument = documents.find((document) => document.id === selectedDocumentId) || null
  const versionsQuery = useQuery({
    queryKey: ['document-versions', selectedDocumentId],
    queryFn: () => fetchDocumentVersions(selectedDocumentId),
    enabled: Boolean(selectedDocumentId),
    staleTime: 4000,
    refetchInterval: selectedDocument && ['pending', 'processing'].includes(selectedDocument.status) ? 2200 : false,
  })
  const versions = versionsQuery.data || []

  useEffect(() => {
    const fallback = latestCompleted(versions)
    if (!fallback) {
      setSelectedVersionId('')
      return
    }
    if (!versions.some((version) => version.id === selectedVersionId)) {
      setSelectedVersionId(fallback.id)
    }
  }, [selectedVersionId, versions])

  const selectedVersion = versions.find((version) => version.id === selectedVersionId) || latestCompleted(versions)
  const chunksQuery = useQuery({
    queryKey: ['document-chunks', selectedVersion?.id || 'none'],
    queryFn: () => fetchDocumentChunks(selectedVersion!.id),
    enabled: Boolean(selectedVersion?.id && selectedVersion.status === 'completed'),
    staleTime: 30000,
  })
  const chunks = chunksQuery.data || []

  const knowledgeQuery = useQuery({
    queryKey: ['knowledge-search', committedQuery],
    queryFn: () => searchKnowledge(committedQuery),
    enabled: committedQuery.length >= 2,
    staleTime: 15000,
  })

  const reingest = useMutation({
    mutationFn: () => {
      if (!selectedDocument) throw new Error('Aucun document sélectionné.')
      return reingestDocument(selectedDocument.id)
    },
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['documents'] }),
        client.invalidateQueries({ queryKey: ['document-versions', selectedDocumentId] }),
        client.invalidateQueries({ queryKey: ['tasks'] }),
        client.invalidateQueries({ queryKey: ['kairo-graph'] }),
      ])
    },
  })

  function submitSearch(event: FormEvent) {
    event.preventDefault()
    const normalized = queryInput.trim()
    setCommittedQuery(normalized.length >= 2 ? normalized : '')
  }

  function selectSearchHit(documentId: string, versionId: string) {
    setSelectedDocumentId(documentId)
    setSelectedVersionId(versionId)
  }

  if (documentsQuery.isLoading) {
    return <div className="workspace-state"><span className="kairo-kicker">CONNAISSANCES</span><strong>Lecture de la bibliothèque canonique…</strong></div>
  }

  return (
    <div className="knowledge-workspace">
      <section className="knowledge-library">
        <header className="workspace-title knowledge-title">
          <div>
            <span className="kairo-kicker">CONNAISSANCES</span>
            <h1>Votre matière première</h1>
            <p>Documents, versions et passages réellement indexés par KAIRO. La recherche ci-dessous interroge les chunks canoniques de la dernière version terminée.</p>
          </div>
          <strong>{documents.length}</strong>
        </header>

        <form className="knowledge-search" onSubmit={submitSearch}>
          <span aria-hidden="true">⌕</span>
          <input
            value={queryInput}
            onChange={(event) => setQueryInput(event.target.value)}
            placeholder="Rechercher dans le contenu indexé…"
          />
          {committedQuery && <button type="button" onClick={() => { setCommittedQuery(''); setQueryInput('') }}>Effacer</button>}
          <button type="submit" disabled={queryInput.trim().length < 2}>Rechercher</button>
        </form>

        {committedQuery && (
          <section className="knowledge-results">
            <div className="knowledge-section-heading">
              <strong>Passages correspondants</strong>
              <span>{knowledgeQuery.data?.results.length || 0} résultat(s)</span>
            </div>
            {knowledgeQuery.isFetching && <div className="knowledge-inline-state">Recherche dans les versions canoniques…</div>}
            {knowledgeQuery.isError && <div className="knowledge-inline-state knowledge-inline-error">{knowledgeQuery.error instanceof Error ? knowledgeQuery.error.message : 'Recherche impossible.'}</div>}
            {!knowledgeQuery.isFetching && knowledgeQuery.data?.results.length === 0 && (
              <div className="knowledge-inline-state">Aucun passage indexé ne contient cette expression.</div>
            )}
            <div className="knowledge-hit-list">
              {knowledgeQuery.data?.results.map((hit) => (
                <button key={hit.chunk_id} type="button" onClick={() => selectSearchHit(hit.document_id, hit.version_id)}>
                  <div><strong>{hit.document_title}</strong><small>génération {hit.generation} · passage {hit.ordinal + 1}</small></div>
                  <p>{hit.excerpt}</p>
                </button>
              ))}
            </div>
          </section>
        )}

        <div className="knowledge-document-list">
          {documents.length === 0 ? (
            <div className="workspace-empty"><strong>La bibliothèque est vide.</strong><span>Importez un premier document : il sera stocké, versionné puis indexé par KAIRO.</span></div>
          ) : documents.map((document) => (
            <button
              key={document.id}
              type="button"
              className={document.id === selectedDocumentId ? 'knowledge-document-active' : ''}
              onClick={() => { setSelectedDocumentId(document.id); setSelectedVersionId('') }}
            >
              <i className={`knowledge-doc-state knowledge-doc-state-${document.status}`} />
              <div>
                <strong>{document.title}</strong>
                <small>{mediaLabel(document.media_type)} · {projectById.get(document.project_id)?.name || 'Bibliothèque'} · {documentStatus(document.status)}</small>
              </div>
              <span>{shortDate(document.updated_at)}</span>
            </button>
          ))}
        </div>
      </section>

      <aside className="knowledge-inspector">
        <UploadDocument projects={projects} onUploaded={(document) => setSelectedDocumentId(document.id)} />

        {selectedDocument && (
          <section className="knowledge-detail">
            <div className="knowledge-detail-heading">
              <div><span className="kairo-kicker">DOCUMENT</span><h2>{selectedDocument.title}</h2></div>
              <button type="button" onClick={() => onExploreEntity({ entity_type: 'document', entity_id: selectedDocument.id })}>Cerveau ↗</button>
            </div>
            <div className="knowledge-detail-meta">
              <span>{mediaLabel(selectedDocument.media_type)}</span>
              <span>{documentStatus(selectedDocument.status)}</span>
              <span>{shortDate(selectedDocument.updated_at)}</span>
            </div>

            {versions.length > 0 && (
              <label className="knowledge-version-select">
                <span>Version</span>
                <select value={selectedVersion?.id || ''} onChange={(event) => setSelectedVersionId(event.target.value)}>
                  {versions.map((version) => (
                    <option key={version.id} value={version.id}>
                      Génération {version.generation} · {version.status} · {version.chunk_count} passages
                    </option>
                  ))}
                </select>
              </label>
            )}

            {selectedVersion && (
              <div className="knowledge-version-meta">
                <span><strong>{selectedVersion.parser}</strong> parseur</span>
                <span><strong>{selectedVersion.chunk_count}</strong> passages</span>
                <span><strong>g{selectedVersion.generation}</strong> génération</span>
              </div>
            )}

            {selectedVersion?.last_error && <p className="workspace-error">{selectedVersion.last_error}</p>}

            <div className="knowledge-preview">
              <div className="knowledge-section-heading"><strong>Contenu indexé</strong><span>{chunks.length} passage(s)</span></div>
              {chunksQuery.isFetching && <div className="knowledge-inline-state">Chargement des passages…</div>}
              {!chunksQuery.isFetching && selectedVersion?.status !== 'completed' && (
                <div className="knowledge-inline-state">Cette version n’est pas encore disponible pour la lecture.</div>
              )}
              {chunks.slice(0, 14).map((chunk) => (
                <article key={chunk.id}>
                  <small>#{chunk.ordinal + 1}</small>
                  <p>{chunk.text}</p>
                </article>
              ))}
              {chunks.length > 14 && <div className="knowledge-preview-more">+ {chunks.length - 14} passages conservés dans KAIRO</div>}
            </div>

            <button
              type="button"
              className="knowledge-reingest"
              disabled={reingest.isPending || selectedDocument.status === 'processing'}
              onClick={() => reingest.mutate()}
            >
              {reingest.isPending ? 'Relance…' : 'Réindexer depuis la source canonique'}
            </button>
            {reingest.isError && <small className="workspace-error">{reingest.error instanceof Error ? reingest.error.message : 'Réindexation impossible.'}</small>}
          </section>
        )}
      </aside>
    </div>
  )
}
