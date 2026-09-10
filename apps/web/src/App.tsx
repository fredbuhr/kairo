import { FormEvent, useEffect, useState } from 'react'

import CockpitShell from './CockpitShell'
import CommandCenterPanel from './CommandCenterPanel'
import KnowledgeWorkspace from './KnowledgeWorkspace'
import NewsWorkspacePanel, {
  type NewsBrief,
  type NewsMode,
  type NewsOutput,
} from './NewsWorkspacePanel'
import ProjectsWorkspace from './ProjectsWorkspace'
import ResearchWorkspace from './ResearchWorkspace'
import { kairoFetch } from './lib/apiClient'
import { useProjectSelection } from './lib/projectSelection'
import {
  type CapabilityTaskView,
  isTerminalTaskStatus,
  loadCapabilityTask,
} from './taskTracking'

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

type NewsRun = {
  task_id: string
  status: string
  query: string
  mode: string
  output: string
}

type RouteParameters = {
  query?: string
  mode?: NewsMode
  location?: string | null
  output?: NewsOutput
}

type AssistantRun = {
  command_id: string
  conversation_id: string
  status: string
  routing: 'deterministic' | 'semantic'
  capability?: string | null
  confidence?: number | null
  route_reason: string
  parameters: RouteParameters
  task_id?: string | null
  routing_task_id?: string | null
}

type CommandState = {
  id: string
  conversation_id: string
  capability_key?: string | null
  status: string
  confidence?: number | string | null
  route_reason?: string | null
  parameters_json: RouteParameters
  task_id?: string | null
}

type KnowledgeSearchResult = {
  document_id: string
  document_project_id: string
  document_title: string
  document_version_id: string
  generation: number
  chunk_id: string
  ordinal: number
  excerpt: string
  content_sha256: string
  rank: number
}

async function readCoreJson<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    const message = typeof detail === 'string' ? detail : detail?.message
    throw new Error(message || `KAIRO Core répond ${response.status}`)
  }
  return body as T
}

function KnowledgeSearchPanel({
  apiUrl,
  onSelectDocument,
}: {
  apiUrl: string
  onSelectDocument: (documentId: string) => void
}) {
  const { selectedProjectId } = useProjectSelection()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<KnowledgeSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setResults([])
    setSearched(false)
    setError(null)
  }, [selectedProjectId])

  async function submitKnowledgeSearch(event: FormEvent) {
    event.preventDefault()
    const trimmed = query.trim()
    if (!selectedProjectId || trimmed.length < 2 || searching) return

    setSearching(true)
    setError(null)
    setSearched(false)
    try {
      const params = new URLSearchParams({
        project_id: selectedProjectId,
        q: trimmed,
        limit: '20',
      })
      const response = await kairoFetch(`${apiUrl}/v1/knowledge/search?${params.toString()}`)
      const loaded = await readCoreJson<KnowledgeSearchResult[]>(response)
      setResults(loaded)
      setSearched(true)
    } catch (searchError) {
      setResults([])
      setSearched(true)
      setError(
        searchError instanceof Error
          ? searchError.message
          : 'Impossible de rechercher dans Knowledge.',
      )
    } finally {
      setSearching(false)
    }
  }

  return (
    <section className="news-workspace" aria-labelledby="knowledge-search-heading">
      <div className="news-heading">
        <div>
          <span className="eyebrow">KNOWLEDGE SEARCH</span>
          <h2 id="knowledge-search-heading">Recherche texte dans les chunks canoniques du projet.</h2>
        </div>
        {searched && <span className="run-state">{results.length} résultat(s)</span>}
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
            <span>20 maximum · dernière version complétée</span>
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
                  <button type="button" onClick={() => onSelectDocument(result.document_id)}>
                    Inspecter ce Document
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

export default function App() {
  const [command, setCommand] = useState('Quelles sont les nouvelles du jour sur la ville de Paris ?')
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [pendingCommandId, setPendingCommandId] = useState<string | null>(null)
  const [lastRoute, setLastRoute] = useState<AssistantRun | null>(null)

  const [query, setQuery] = useState('Quelles sont les nouvelles du jour sur la ville de Paris ?')
  const [mode, setMode] = useState<NewsMode>('local')
  const [location, setLocation] = useState('Paris')
  const [output, setOutput] = useState<NewsOutput>('both')

  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskCapability, setTaskCapability] = useState<string | null>(null)
  const [taskView, setTaskView] = useState<CapabilityTaskView | null>(null)
  const [brief, setBrief] = useState<NewsBrief | null>(null)
  const [selectedKnowledgeDocumentId, setSelectedKnowledgeDocumentId] = useState('')

  const [submitting, setSubmitting] = useState(false)
  const [routing, setRouting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!pendingCommandId) return
    let cancelled = false
    let timer: number | undefined

    const poll = async () => {
      try {
        const response = await kairoFetch(`${API_URL}/v1/commands/${pendingCommandId}`)
        if (!response.ok) throw new Error(`KAIRO Core répond ${response.status}`)
        const state = (await response.json()) as CommandState
        if (cancelled) return

        if (state.status === 'accepted' && state.task_id && state.capability_key) {
          const parameters = state.parameters_json || {}
          setLastRoute({
            command_id: state.id,
            conversation_id: state.conversation_id,
            status: 'accepted',
            routing: 'semantic',
            capability: state.capability_key,
            confidence: state.confidence == null ? null : Number(state.confidence),
            route_reason: state.route_reason || 'semantic.model',
            parameters,
            task_id: state.task_id,
          })
          setTaskCapability(state.capability_key)
          setTaskId(state.task_id)
          setQuery(parameters.query || command)
          if (parameters.mode) setMode(parameters.mode)
          if (parameters.output) setOutput(parameters.output)
          setLocation(parameters.location || '')
          setPendingCommandId(null)
          return
        }

        if (state.status === 'unsupported') {
          setPendingCommandId(null)
          setError('KAIRO n’a pas encore de capacité enregistrée capable de traiter cette demande en sécurité.')
          return
        }
        if (state.status === 'failed') {
          setPendingCommandId(null)
          setError('Le routage sémantique KAIRO a échoué. La demande n’a pas été exécutée.')
          return
        }
        timer = window.setTimeout(poll, 700)
      } catch (pollError) {
        if (!cancelled) {
          setPendingCommandId(null)
          setError(
            pollError instanceof Error
              ? pollError.message
              : 'Impossible de suivre le routage sémantique.',
          )
        }
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [pendingCommandId, command])

  useEffect(() => {
    if (!taskId || !taskCapability) return
    let cancelled = false
    let timer: number | undefined

    const poll = async () => {
      try {
        const data = await loadCapabilityTask(API_URL, taskCapability, taskId)
        if (cancelled) return
        setTaskView(data)
        setBrief(taskCapability === 'news.brief' ? (data.raw as NewsBrief) : null)
        if (data.status === 'failed' && data.error) setError(data.error)
        if (!isTerminalTaskStatus(data.status)) timer = window.setTimeout(poll, 1200)
      } catch (pollError) {
        if (!cancelled) {
          setError(
            pollError instanceof Error ? pollError.message : 'Impossible de suivre la tâche KAIRO.',
          )
        }
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [taskId, taskCapability])

  function resetTaskSurface() {
    setError(null)
    setBrief(null)
    setTaskView(null)
    setTaskCapability(null)
    setTaskId(null)
    setLastRoute(null)
  }

  async function submitCommand(event: FormEvent) {
    event.preventDefault()
    if (!command.trim()) return
    setRouting(true)
    setPendingCommandId(null)
    resetTaskSurface()

    try {
      const response = await kairoFetch(`${API_URL}/v1/assistant/commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: command,
          conversation_id: conversationId,
          locale: 'fr-FR',
          output: 'auto',
        }),
      })
      const responseBody = await response.json().catch(() => null)
      if (!response.ok) {
        const detail = responseBody?.detail
        if (detail?.conversation_id) setConversationId(detail.conversation_id)
        throw new Error(
          detail?.message || `KAIRO ne sait pas encore router cette demande (${response.status}).`,
        )
      }

      const run = responseBody as AssistantRun
      setLastRoute(run)
      setConversationId(run.conversation_id)
      if (run.status === 'routing' && run.routing === 'semantic') {
        setPendingCommandId(run.command_id)
        return
      }
      if (!run.task_id || !run.capability) {
        throw new Error('KAIRO a accepté la commande sans fournir de capacité finale.')
      }

      setTaskCapability(run.capability)
      setTaskId(run.task_id)
      setQuery(run.parameters.query || command)
      if (run.parameters.mode) setMode(run.parameters.mode)
      if (run.parameters.output) setOutput(run.parameters.output)
      setLocation(run.parameters.location || '')
    } catch (routeError) {
      setError(routeError instanceof Error ? routeError.message : 'Impossible de router la commande.')
    } finally {
      setRouting(false)
    }
  }

  async function submitNews(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setPendingCommandId(null)
    resetTaskSurface()

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
      setTaskCapability('news.brief')
      setTaskId(run.task_id)
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : 'Impossible de lancer le briefing.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  const commandPanel = (
    <CommandCenterPanel
      command={command}
      conversationId={conversationId}
      pendingCommandId={pendingCommandId}
      routing={routing}
      route={lastRoute}
      task={taskView}
      error={error}
      onCommandChange={setCommand}
      onSubmit={submitCommand}
      onUseExample={(value) => {
        setCommand(value)
        setError(null)
      }}
    />
  )

  const newsPanel = (
    <NewsWorkspacePanel
      apiUrl={API_URL}
      query={query}
      mode={mode}
      location={location}
      output={output}
      brief={brief}
      submitting={submitting}
      running={Boolean(taskId && taskCapability === 'news.brief')}
      error={error}
      onQueryChange={setQuery}
      onModeChange={setMode}
      onLocationChange={setLocation}
      onOutputChange={setOutput}
      onSubmit={submitNews}
    />
  )

  return (
    <main className="shell">
      <header>
        <div>
          <span className="eyebrow">PERSONAL AI OPERATING SYSTEM</span>
          <h1>KAIRO</h1>
        </div>
        <span className="status">cockpit + durable command kernel</span>
      </header>

      <section className="hero">
        <h2>One interface. One world model. Replaceable engines.</h2>
        <p>
          Canonical state, durable workflows, policy, events and specialist capabilities behind one
          persistent conversational command surface.
        </p>
      </section>

      <CockpitShell
        slots={{
          command: commandPanel,
          news: newsPanel,
          research: <ResearchWorkspace apiUrl={API_URL} />,
        }}
        extraPanels={[
          {
            key: 'projects',
            id: 'projects-workspace',
            title: 'Projects',
            content: <ProjectsWorkspace apiUrl={API_URL} />,
          },
          {
            key: 'knowledge',
            id: 'knowledge-workspace',
            title: 'Knowledge',
            content: (
              <>
                <KnowledgeSearchPanel
                  apiUrl={API_URL}
                  onSelectDocument={setSelectedKnowledgeDocumentId}
                />
                <KnowledgeWorkspace
                  apiUrl={API_URL}
                  selectedDocumentId={selectedKnowledgeDocumentId}
                  onSelectedDocumentIdChange={setSelectedKnowledgeDocumentId}
                />
              </>
            ),
          },
        ]}
      />

      <section className="grid" aria-label="KAIRO spaces">
        {spaces.map((space) => (
          <article
            key={space}
            className={`card ${['Command Center', 'Knowledge', 'News Intelligence', 'Research'].includes(space) ? 'card-active' : ''}`}
          >
            <span>{space}</span>
            <small>
              {space === 'Command Center'
                ? 'dockable command surface'
                : ['Knowledge', 'News Intelligence', 'Research'].includes(space)
                  ? 'dockable working capability'
                  : 'planned workspace'}
            </small>
          </article>
        ))}
      </section>
    </main>
  )
}
