import { FormEvent, useEffect, useMemo, useState } from 'react'

import { kairoFetch } from './lib/apiClient'
import { useProjectSelection } from './lib/projectSelection'

type Project = {
  id: string
  name: string
  status: string
}

type ResearchClaim = {
  text: string
  evidence_ids: string[]
  confidence: 'low' | 'medium' | 'high' | 'unknown'
}

type ResearchEvidence = {
  evidence_id: string
  source_type: 'tool' | 'document' | 'memory' | 'unknown'
  source: string
  authority: string
  tool_key?: string | null
  invocation_id?: string | null
  title?: string | null
  excerpt?: string | null
}

type ResearchRun = {
  task_id: string
  project_id: string
  status: string
  execution_status?: string | null
  query: string
  answer?: string | null
  synthesis?: {
    answer: string
    claims: ResearchClaim[]
    uncertainties: string[]
  } | null
  evidence: ResearchEvidence[]
  tool_call_count: number
  planner_model_alias?: string | null
  synthesis_model_alias?: string | null
  model_budget_usd?: string | number | null
  artifact_id?: string | null
  correlation_id?: string | null
  error?: string | null
}

type ResearchAccepted = {
  task_id: string
  status: string
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

function sourceLabel(evidence: ResearchEvidence) {
  if (evidence.source_type === 'document') return 'Document KAIRO'
  if (evidence.source_type === 'memory') return 'Mémoire dérivée'
  if (evidence.source_type === 'tool') return evidence.tool_key || evidence.source || 'Outil MCP'
  return evidence.source || 'Contexte'
}

export default function ResearchWorkspace({ apiUrl }: Props) {
  const [projects, setProjects] = useState<Project[]>([])
  const { selectedProjectId: projectId, setSelectedProjectId: setProjectId } = useProjectSelection()
  const [query, setQuery] = useState('')
  const [maxToolCalls, setMaxToolCalls] = useState(3)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [run, setRun] = useState<ResearchRun | null>(null)
  const [loadingProjects, setLoadingProjects] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const loadProjects = async () => {
      try {
        const response = await kairoFetch(`${apiUrl}/v1/projects`)
        const data = await readJson<Project[]>(response)
        if (cancelled) return
        const active = data.filter((project) => project.status === 'active')
        setProjects(active)
        setProjectId((current) => {
          if (current && active.some((project) => project.id === current)) return current
          return active[0]?.id || ''
        })
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Impossible de charger les projets.')
        }
      } finally {
        if (!cancelled) setLoadingProjects(false)
      }
    }

    void loadProjects()
    return () => {
      cancelled = true
    }
  }, [apiUrl, setProjectId])

  useEffect(() => {
    if (!taskId) return
    let cancelled = false
    let timer: number | undefined

    const poll = async () => {
      try {
        const response = await kairoFetch(`${apiUrl}/v1/research/runs/${taskId}`)
        const data = await readJson<ResearchRun>(response)
        if (cancelled) return
        setRun(data)
        if (!['completed', 'failed'].includes(data.status)) {
          timer = window.setTimeout(poll, 1200)
        }
      } catch (pollError) {
        if (!cancelled) {
          setError(pollError instanceof Error ? pollError.message : 'Impossible de suivre la recherche.')
        }
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [apiUrl, taskId])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!projectId || query.trim().length < 3) return
    setSubmitting(true)
    setError(null)
    setRun(null)
    setTaskId(null)
    try {
      const response = await kairoFetch(`${apiUrl}/v1/research/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          query: query.trim(),
          max_tool_calls: maxToolCalls,
          allowed_tool_keys: [],
          model_alias: 'local-fast',
          estimated_model_cost_usd: '0.01',
        }),
      })
      const accepted = await readJson<ResearchAccepted>(response)
      setTaskId(accepted.task_id)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Impossible de lancer Research.')
    } finally {
      setSubmitting(false)
    }
  }

  const evidenceById = useMemo(
    () => new Map((run?.evidence || []).map((item) => [item.evidence_id, item])),
    [run],
  )

  return (
    <section className="news-workspace" aria-labelledby="research-heading">
      <div className="news-heading">
        <div>
          <span className="eyebrow">RESEARCH</span>
          <h2 id="research-heading">Recherche autonome avec preuves inspectables.</h2>
        </div>
        {run && <span className={`run-state run-state-${run.status}`}>{run.status}</span>}
      </div>

      <form className="news-form" onSubmit={submit}>
        <label className="query-field">
          <span>Question</span>
          <textarea
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            rows={3}
            minLength={3}
            required
            placeholder="Ex. Compare l’état actuel de mon projet avec les informations récentes disponibles."
          />
        </label>

        <div className="news-controls">
          <label>
            <span>Projet</span>
            <select
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              disabled={loadingProjects || projects.length === 0}
            >
              {projects.length === 0 && <option value="">Aucun projet actif</option>}
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Appels outils max.</span>
            <select value={maxToolCalls} onChange={(event) => setMaxToolCalls(Number(event.target.value))}>
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>

          <button type="submit" disabled={submitting || !projectId || query.trim().length < 3}>
            {submitting ? 'Lancement…' : 'Lancer Research'}
          </button>
        </div>
      </form>

      {error && <div className="error-panel">{error}</div>}

      {taskId && run && !['completed', 'failed'].includes(run.status) && !error && (
        <div className="progress-panel">
          <strong>KAIRO construit une réponse durable et vérifiable.</strong>
          <span>
            {run.execution_status || run.status} · {run.tool_call_count} appel(s) outil enregistré(s)
          </span>
        </div>
      )}

      {run?.status === 'failed' && (
        <div className="error-panel">{run.error || 'La recherche KAIRO a échoué.'}</div>
      )}

      {run?.status === 'completed' && run.answer && (
        <article className="briefing">
          <div className="briefing-topline">
            <div>
              <span className="eyebrow">SYNTHÈSE GROUNDED</span>
              <h3>{run.query}</h3>
            </div>
            <div className="impact-score">
              <strong>{run.evidence.length}</strong>
              <span> preuve(s)</span>
            </div>
          </div>

          <div className="brief-summary">{run.answer}</div>

          {run.synthesis?.claims.length ? (
            <section className="sources" aria-label="Affirmations et preuves Research">
              <div className="sources-title">
                <strong>Affirmations vérifiables</strong>
                <span>{run.synthesis.claims.length} conclusion(s)</span>
              </div>
              <div className="source-list">
                {run.synthesis.claims.map((claim, index) => (
                  <div className="source-card" key={`${claim.text}-${index}`}>
                    <span className="source-id">{claim.confidence}</span>
                    <div>
                      <strong>{claim.text}</strong>
                      <small>
                        {claim.evidence_ids
                          .map((id) => `${id} · ${sourceLabel(evidenceById.get(id) || { evidence_id: id, source_type: 'unknown', source: 'unknown', authority: 'unknown' })}`)
                          .join(' · ')}
                      </small>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {run.evidence.length > 0 && (
            <section className="sources" aria-label="Preuves Research">
              <div className="sources-title">
                <strong>Preuves et contexte</strong>
                <span>Documents canoniques, mémoire dérivée et outils MCP restent distingués.</span>
              </div>
              <div className="source-list">
                {run.evidence.map((item) => (
                  <div className="source-card" key={item.evidence_id}>
                    <span className="source-id">{item.evidence_id}</span>
                    <div>
                      <strong>{item.title || sourceLabel(item)}</strong>
                      <small>{item.authority} · {item.source_type}</small>
                      {item.excerpt && <small>{item.excerpt}</small>}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {run.synthesis?.uncertainties.length ? (
            <div className="impact-panel">
              <span>Incertitudes conservées</span>
              <p>{run.synthesis.uncertainties.join(' · ')}</p>
            </div>
          ) : null}
        </article>
      )}
    </section>
  )
}
