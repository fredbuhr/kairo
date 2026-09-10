import { type FormEventHandler, useEffect, useState } from 'react'

import { kairoFetch } from './lib/apiClient'

export type NewsSource = {
  id: string
  title: string
  url: string
  domain?: string
  snippet?: string
  published_at?: string | null
  market_score?: number
}

export type MarketImpact = {
  score?: number
  level?: string
  direction?: string
  rationale?: string
  affected_sectors?: string[]
  affected_assets?: string[]
}

export type NewsArtifact = {
  id: string
  title: string
  content: {
    query?: string
    mode?: string
    generated_at?: string
    summary?: string
    spoken_summary?: string
    market_impact?: MarketImpact | null
    sources?: NewsSource[]
    model_warning?: string | null
  }
}

export type NewsBrief = {
  task_id: string
  status: string
  query: string
  mode: string
  output: string
  voice: string
  artifact?: NewsArtifact | null
  audio_available: boolean
}

export type NewsMode = 'general' | 'local' | 'market_impact'
export type NewsOutput = 'text' | 'audio' | 'both'

type NewsWorkspacePanelProps = {
  apiUrl: string
  query: string
  mode: NewsMode
  location: string
  output: NewsOutput
  brief: NewsBrief | null
  submitting: boolean
  running: boolean
  error: string | null
  onQueryChange: (value: string) => void
  onModeChange: (value: NewsMode) => void
  onLocationChange: (value: string) => void
  onOutputChange: (value: NewsOutput) => void
  onSubmit: FormEventHandler<HTMLFormElement>
}

type AuthenticatedNewsAudioProps = {
  apiUrl: string
  taskId: string
  voice: string
}

function impactLabel(level?: string) {
  const labels: Record<string, string> = {
    low: 'Faible',
    medium: 'Modéré',
    high: 'Élevé',
    critical: 'Critique',
  }
  return labels[level || ''] || level || 'Non évalué'
}

function AuthenticatedNewsAudio({ apiUrl, taskId, voice }: AuthenticatedNewsAudioProps) {
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [loadingAudio, setLoadingAudio] = useState(false)
  const [audioError, setAudioError] = useState<string | null>(null)

  useEffect(() => {
    setAudioUrl(null)
    setAudioError(null)
    setLoadingAudio(false)
  }, [taskId, voice])

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl)
    }
  }, [audioUrl])

  async function loadAudio() {
    if (loadingAudio || audioUrl) return
    setLoadingAudio(true)
    setAudioError(null)
    try {
      const response = await kairoFetch(
        `${apiUrl}/v1/news/briefs/${taskId}/audio?voice=${encodeURIComponent(voice)}`,
      )
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        const detail = body?.detail
        const message = typeof detail === 'string' ? detail : detail?.message
        throw new Error(message || `Impossible de charger l’audio (${response.status}).`)
      }
      const blob = await response.blob()
      setAudioUrl(URL.createObjectURL(blob))
    } catch (loadError) {
      setAudioError(
        loadError instanceof Error ? loadError.message : 'Impossible de charger la lecture audio.',
      )
    } finally {
      setLoadingAudio(false)
    }
  }

  if (!audioUrl) {
    return (
      <div>
        <button type="button" onClick={() => void loadAudio()} disabled={loadingAudio}>
          {loadingAudio ? 'Préparation audio…' : 'Charger l’audio'}
        </button>
        {audioError && <small>{audioError}</small>}
      </div>
    )
  }

  return <audio controls autoPlay preload="none" src={audioUrl} />
}

export default function NewsWorkspacePanel({
  apiUrl,
  query,
  mode,
  location,
  output,
  brief,
  submitting,
  running,
  error,
  onQueryChange,
  onModeChange,
  onLocationChange,
  onOutputChange,
  onSubmit,
}: NewsWorkspacePanelProps) {
  const sources = brief?.artifact?.content.sources || []
  const impact = brief?.artifact?.content.market_impact

  return (
    <section className="news-workspace" aria-labelledby="news-heading">
      <div className="news-heading">
        <div>
          <span className="eyebrow">NEWS INTELLIGENCE</span>
          <h2 id="news-heading">Briefing sourcé, lisible ou oral.</h2>
        </div>
        {brief && <span className={`run-state run-state-${brief.status}`}>{brief.status}</span>}
      </div>

      <form className="news-form" onSubmit={onSubmit}>
        <label className="query-field">
          <span>Question</span>
          <textarea
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            rows={3}
            minLength={2}
            required
            placeholder="Quelles nouvelles risquent d'impacter la bourse aujourd'hui ?"
          />
        </label>

        <div className="news-controls">
          <label>
            <span>Analyse</span>
            <select value={mode} onChange={(event) => onModeChange(event.target.value as NewsMode)}>
              <option value="general">Actualité générale</option>
              <option value="local">Actualité locale</option>
              <option value="market_impact">Impact marchés / bourse</option>
            </select>
          </label>

          {mode === 'local' && (
            <label>
              <span>Lieu</span>
              <input value={location} onChange={(event) => onLocationChange(event.target.value)} />
            </label>
          )}

          <label>
            <span>Sortie</span>
            <select value={output} onChange={(event) => onOutputChange(event.target.value as NewsOutput)}>
              <option value="text">Texte</option>
              <option value="audio">Audio</option>
              <option value="both">Texte + audio</option>
            </select>
          </label>

          <button type="submit" disabled={submitting || !query.trim()}>
            {submitting ? 'Lancement…' : 'Créer le briefing'}
          </button>
        </div>
      </form>

      {error && <div className="error-panel">{error}</div>}

      {running && !brief?.artifact && !error && (
        <div className="progress-panel">
          <strong>KAIRO recherche et recoupe les sources.</strong>
          <span>La tâche est durable : elle peut reprendre après un redémarrage du Worker.</span>
        </div>
      )}

      {brief?.artifact && (
        <article className="briefing">
          <div className="briefing-topline">
            <div>
              <span className="eyebrow">BRIEFING SOURCÉ</span>
              <h3>{brief.artifact.title}</h3>
            </div>
            {impact && (
              <div className="impact-score">
                <strong>{Math.round(impact.score || 0)}</strong>
                <span>/100 · {impactLabel(impact.level)}</span>
              </div>
            )}
          </div>

          {impact?.rationale && (
            <div className="impact-panel">
              <span>Impact marchés · {impact.direction || 'incertain'}</span>
              <p>{impact.rationale}</p>
            </div>
          )}

          {brief.output !== 'audio' && (
            <div className="brief-summary">{brief.artifact.content.summary}</div>
          )}

          {brief.output !== 'text' && (
            <div className="audio-panel">
              <div>
                <strong>Lecture KAIRO</strong>
                <small>Voix locale Kokoro · français</small>
              </div>
              <AuthenticatedNewsAudio
                key={`${brief.task_id}:${brief.voice}`}
                apiUrl={apiUrl}
                taskId={brief.task_id}
                voice={brief.voice}
              />
            </div>
          )}

          {brief.artifact.content.model_warning && (
            <p className="warning">{brief.artifact.content.model_warning}</p>
          )}

          <section className="sources" aria-label="Sources du briefing">
            <div className="sources-title">
              <strong>Sources</strong>
              <span>{sources.length} résultats conservés avec le briefing</span>
            </div>
            <div className="source-list">
              {sources.map((source) => (
                <a key={source.id} href={source.url} target="_blank" rel="noreferrer" className="source-card">
                  <span className="source-id">{source.id}</span>
                  <div>
                    <strong>{source.title}</strong>
                    <small>
                      {source.domain || 'source'}
                      {source.published_at ? ` · ${source.published_at}` : ''}
                    </small>
                  </div>
                </a>
              ))}
            </div>
          </section>
        </article>
      )}
    </section>
  )
}
