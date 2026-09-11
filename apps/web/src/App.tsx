import { FormEvent, useEffect, useState } from 'react'

import CockpitShell from './CockpitShell'
import CommandCenterPanel from './CommandCenterPanel'
import KnowledgePanel from './KnowledgePanel'
import NewsWorkspacePanel, {
  type NewsBrief,
  type NewsMode,
  type NewsOutput,
} from './NewsWorkspacePanel'
import ProjectsWorkspace from './ProjectsWorkspace'
import ResearchWorkspace from './ResearchWorkspace'
import TodayWorkspace from './TodayWorkspace'
import { nevoliumFetch } from './lib/apiClient'
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

const activeSpaces = new Set([
  'Command Center',
  'Today',
  'Projects',
  'Knowledge',
  'News Intelligence',
  'Research',
])

const API_URL = (import.meta.env.VITE_NEVOLIUM_API_URL || 'http://localhost:8000').replace(/\/$/, '')

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

  const [submitting, setSubmitting] = useState(false)
  const [routing, setRouting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!pendingCommandId) return
    let cancelled = false
    let timer: number | undefined

    const poll = async () => {
      try {
        const response = await nevoliumFetch(`${API_URL}/v1/commands/${pendingCommandId}`)
        if (!response.ok) throw new Error(`Nevolium Core répond ${response.status}`)
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
          setError('Nevolium n’a pas encore de capacité enregistrée capable de traiter cette demande en sécurité.')
          return
        }
        if (state.status === 'failed') {
          setPendingCommandId(null)
          setError('Le routage sémantique Nevolium a échoué. La demande n’a pas été exécutée.')
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
            pollError instanceof Error ? pollError.message : 'Impossible de suivre la tâche Nevolium.',
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
      const response = await nevoliumFetch(`${API_URL}/v1/assistant/commands`, {
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
          detail?.message || `Nevolium ne sait pas encore router cette demande (${response.status}).`,
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
        throw new Error('Nevolium a accepté la commande sans fournir de capacité finale.')
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
      const response = await nevoliumFetch(`${API_URL}/v1/news/briefs`, {
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
          <h1>Nevolium</h1>
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
            key: 'today',
            id: 'today-workspace',
            title: 'Today',
            content: <TodayWorkspace apiUrl={API_URL} />,
            minimumWidth: 360,
          },
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
            content: <KnowledgePanel apiUrl={API_URL} />,
          },
        ]}
      />

      <section className="grid" aria-label="Nevolium spaces">
        {spaces.map((space) => (
          <article
            key={space}
            className={`card ${activeSpaces.has(space) ? 'card-active' : ''}`}
          >
            <span>{space}</span>
            <small>
              {space === 'Command Center'
                ? 'dockable command surface'
                : activeSpaces.has(space)
                  ? 'dockable working capability'
                  : 'planned workspace'}
            </small>
          </article>
        ))}
      </section>
    </main>
  )
}
