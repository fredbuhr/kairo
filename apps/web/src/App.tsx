import { FormEvent, useEffect, useMemo, useState } from 'react'

const spaces = [
  'Command Center',
  'Today',
  'Projects',
  'Knowledge',
  'Mind 2D / 3D',
  'Gantt',
  'Calendar',
  'People',
  'News Intelligence',
  'Research',
  'Automations',
  'Agents',
  'Developer',
  'Crypto',
  'Finance',
  'Home',
  'Analytics',
  'Maps',
  'Approvals',
  'Activity',
  'System',
]

const API_URL = (import.meta.env.VITE_KAIRO_API_URL || 'http://localhost:8000').replace(/\/$/, '')

type NewsSource = {
  id: string
  title: string
  url: string
  domain?: string
  snippet?: string
  published_at?: string | null
  market_score?: number
}

type MarketImpact = {
  score?: number
  level?: string
  direction?: string
  rationale?: string
  affected_sectors?: string[]
  affected_assets?: string[]
}

type NewsArtifact = {
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

type NewsBrief = {
  task_id: string
  status: string
  query: string
  mode: string
  output: string
  voice: string
  artifact?: NewsArtifact | null
  audio_available: boolean
}

type NewsRun = {
  task_id: string
  status: string
  query: string
  mode: string
  output: string
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

export default function App() {
  const [query, setQuery] = useState('Quelles sont les nouvelles du jour sur la ville de Paris ?')
  const [mode, setMode] = useState<'general' | 'local' | 'market_impact'>('local')
  const [location, setLocation] = useState('Paris')
  const [output, setOutput] = useState<'text' | 'audio' | 'both'>('both')
  const [taskId, setTaskId] = useState<string | null>(null)
  const [brief, setBrief] = useState<NewsBrief | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!taskId) return
    let cancelled = false
    let timer: number | undefined

    const poll = async () => {
      try {
        const response = await fetch(`${API_URL}/v1/news/briefs/${taskId}`)
        if (!response.ok) throw new Error(`KAIRO Core répond ${response.status}`)
        const data = (await response.json()) as NewsBrief
        if (cancelled) return
        setBrief(data)
        if (!['completed', 'failed'].includes(data.status)) {
          timer = window.setTimeout(poll, 1200)
        }
      } catch (pollError) {
        if (!cancelled) {
          setError(pollError instanceof Error ? pollError.message : 'Impossible de lire le briefing.')
        }
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [taskId])

  const sources = useMemo(() => brief?.artifact?.content.sources || [], [brief])
  const impact = brief?.artifact?.content.market_impact

  async function submitNews(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    setBrief(null)
    setTaskId(null)
    try {
      const response = await fetch(`${API_URL}/v1/news/briefs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          mode,
          location: mode === 'local' ? location || null : null,
          language: 'fr',
          time_range: 'day',
          max_sources: 10,
          output,
          voice: 'ff_siwis',
        }),
      })
      if (!response.ok) {
        const body = await response.text()
        throw new Error(`Impossible de lancer le briefing (${response.status}) : ${body}`)
      }
      const run = (await response.json()) as NewsRun
      setTaskId(run.task_id)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Impossible de lancer le briefing.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="shell">
      <header>
        <div>
          <span className="eyebrow">PERSONAL AI OPERATING SYSTEM</span>
          <h1>KAIRO</h1>
        </div>
        <span className="status">foundation + news intelligence</span>
      </header>

      <section className="hero">
        <h2>One interface. One world model. Replaceable engines.</h2>
        <p>
          Canonical state, durable workflows, policy, events, memory projections, realtime
          collaboration and specialist adapters — now including sourced, readable and spoken news.
        </p>
      </section>

      <section className="news-workspace" aria-labelledby="news-heading">
        <div className="news-heading">
          <div>
            <span className="eyebrow">NEWS INTELLIGENCE</span>
            <h2 id="news-heading">Demande à KAIRO ce qui compte aujourd'hui.</h2>
          </div>
          {brief && <span className={`run-state run-state-${brief.status}`}>{brief.status}</span>}
        </div>

        <form className="news-form" onSubmit={submitNews}>
          <label className="query-field">
            <span>Question</span>
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              rows={3}
              minLength={2}
              required
              placeholder="Quelles nouvelles risquent d'impacter la bourse aujourd'hui ?"
            />
          </label>

          <div className="news-controls">
            <label>
              <span>Analyse</span>
              <select value={mode} onChange={(event) => setMode(event.target.value as typeof mode)}>
                <option value="general">Actualité générale</option>
                <option value="local">Actualité locale</option>
                <option value="market_impact">Impact marchés / bourse</option>
              </select>
            </label>

            {mode === 'local' && (
              <label>
                <span>Lieu</span>
                <input value={location} onChange={(event) => setLocation(event.target.value)} />
              </label>
            )}

            <label>
              <span>Sortie</span>
              <select value={output} onChange={(event) => setOutput(event.target.value as typeof output)}>
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

        {taskId && !brief?.artifact && !error && (
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

            {output !== 'audio' && (
              <div className="brief-summary">{brief.artifact.content.summary}</div>
            )}

            {output !== 'text' && (
              <div className="audio-panel">
                <div>
                  <strong>Lecture KAIRO</strong>
                  <small>Voix locale Kokoro · français</small>
                </div>
                <audio
                  controls
                  preload="none"
                  src={`${API_URL}/v1/news/briefs/${brief.task_id}/audio?voice=${encodeURIComponent(brief.voice)}`}
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

      <section className="grid" aria-label="KAIRO spaces">
        {spaces.map((space) => (
          <article key={space} className={`card ${space === 'News Intelligence' ? 'card-active' : ''}`}>
            <span>{space}</span>
            <small>{space === 'News Intelligence' ? 'first working workspace' : 'planned workspace'}</small>
          </article>
        ))}
      </section>
    </main>
  )
}
