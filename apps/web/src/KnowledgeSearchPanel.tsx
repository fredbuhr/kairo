import { type FormEvent, useEffect, useState } from 'react'

import { readKnowledgeJson } from './knowledgeApi'
import type { KnowledgeInspectionTarget, KnowledgeSearchResult } from './knowledgeTypes'
import { kairoFetch } from './lib/apiClient'
import { useProjectSelection } from './lib/projectSelection'

type Props = {
  apiUrl: string
  onInspectResult: (target: KnowledgeInspectionTarget) => void
}

const KNOWLEDGE_SEARCH_PAGE_SIZE = 20

export default function KnowledgeSearchPanel({ apiUrl, onInspectResult }: Props) {
  const { selectedProjectId } = useProjectSelection()
  const [query, setQuery] = useState('')
  const [activeQuery, setActiveQuery] = useState('')
  const [results, setResults] = useState<KnowledgeSearchResult[]>([])
  const [searchOffset, setSearchOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [searching, setSearching] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setActiveQuery('')
    setResults([])
    setSearchOffset(0)
    setHasMore(false)
    setSearched(false)
    setError(null)
  }, [selectedProjectId])

  async function loadKnowledgeSearchPage(searchQuery: string, offset: number) {
    if (!selectedProjectId || searchQuery.length < 2 || searching) return

    const normalizedOffset = Math.max(0, offset)
    setSearching(true)
    setError(null)
    try {
      const params = new URLSearchParams({
        project_id: selectedProjectId,
        q: searchQuery,
        offset: String(normalizedOffset),
        limit: String(KNOWLEDGE_SEARCH_PAGE_SIZE + 1),
      })
      const response = await kairoFetch(`${apiUrl}/v1/knowledge/search?${params.toString()}`)
      const loaded = await readKnowledgeJson<KnowledgeSearchResult[]>(response)
      setActiveQuery(searchQuery)
      setResults(loaded.slice(0, KNOWLEDGE_SEARCH_PAGE_SIZE))
      setSearchOffset(normalizedOffset)
      setHasMore(loaded.length > KNOWLEDGE_SEARCH_PAGE_SIZE)
      setSearched(true)
    } catch (searchError) {
      setError(
        searchError instanceof Error
          ? searchError.message
          : 'Impossible de rechercher dans Knowledge.',
      )
    } finally {
      setSearching(false)
    }
  }

  async function submitKnowledgeSearch(event: FormEvent) {
    event.preventDefault()
    const trimmed = query.trim()
    if (!selectedProjectId || trimmed.length < 2 || searching) return

    setResults([])
    setSearchOffset(0)
    setHasMore(false)
    setSearched(false)
    await loadKnowledgeSearchPage(trimmed, 0)
  }

  const pageStart = searched && results.length > 0 ? searchOffset + 1 : 0
  const pageEnd = searched ? searchOffset + results.length : 0

  return (
    <section className="news-workspace" aria-labelledby="knowledge-search-heading">
      <div className="news-heading">
        <div>
          <span className="eyebrow">KNOWLEDGE SEARCH</span>
          <h2 id="knowledge-search-heading">Recherche texte dans les chunks canoniques du projet.</h2>
        </div>
        {searched && (
          <span className="run-state">
            {pageStart === 0 ? '0 résultat' : `Résultats ${pageStart}–${pageEnd}`}
          </span>
        )}
      </div>

      <form className="news-form" onSubmit={submitKnowledgeSearch}>
        <label className="query-field">
          <span>Recherche</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            minLength={2}
            maxLength={400}
            placeholder="Ex. architecture ownership document"
          />
        </label>
        <div className="news-controls">
          <button
            type="submit"
            disabled={searching || !selectedProjectId || query.trim().length < 2}
          >
            {searching ? 'Recherche…' : 'Rechercher dans ce projet'}
          </button>
        </div>
      </form>

      {!selectedProjectId && (
        <div className="progress-panel">
          <strong>Aucun projet sélectionné.</strong>
          <span>Choisissez un projet dans Projects ou Research avant de lancer la recherche.</span>
        </div>
      )}

      {error && <div className="error-panel">{error}</div>}

      {searched && !error && (
        <section className="sources" aria-label="Résultats Knowledge">
          <div className="sources-title">
            <strong>Résultats canoniques</strong>
            <span>20 par page · dernière version complétée</span>
          </div>

          <div className="news-controls" aria-label="Pagination des résultats Knowledge">
            <button
              type="button"
              onClick={() =>
                void loadKnowledgeSearchPage(
                  activeQuery,
                  Math.max(0, searchOffset - KNOWLEDGE_SEARCH_PAGE_SIZE),
                )
              }
              disabled={searching || searchOffset === 0 || !activeQuery}
            >
              ← Page précédente
            </button>
            <span className="route-chip">
              {pageStart === 0 ? 'Aucun résultat sur cette page' : `${pageStart}–${pageEnd}`}
            </span>
            <button
              type="button"
              onClick={() =>
                void loadKnowledgeSearchPage(
                  activeQuery,
                  searchOffset + KNOWLEDGE_SEARCH_PAGE_SIZE,
                )
              }
              disabled={searching || !hasMore || !activeQuery}
            >
              Page suivante →
            </button>
          </div>

          <div className="source-list">
            {results.length === 0 && (
              <div className="source-card">
                <span className="source-id">0</span>
                <div>
                  <strong>Aucun chunk correspondant.</strong>
                  <small>La recherche reste limitée aux Documents prêts du projet sélectionné.</small>
                </div>
              </div>
            )}
            {results.map((result) => (
              <div className="source-card" key={result.chunk_id}>
                <span className="source-id">#{result.ordinal}</span>
                <div>
                  <strong>{result.document_title}</strong>
                  <small>{result.excerpt}</small>
                  <small>
                    v{result.generation} · score {result.rank.toFixed(3)} · SHA-256{' '}
                    {result.content_sha256.slice(0, 16)}…
                  </small>
                  <button
                    type="button"
                    onClick={() =>
                      onInspectResult({
                        documentId: result.document_id,
                        documentVersionId: result.document_version_id,
                        chunkId: result.chunk_id,
                        ordinal: result.ordinal,
                      })
                    }
                  >
                    Inspecter ce chunk
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </section>
  )
}
