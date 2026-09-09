import { useEffect, useMemo, useState } from 'react'

import { API_URL, apiJson } from '../../lib/api'
import { authenticatedFetch } from '../../lib/authSession'

export type RouteParameters = {
  query?: string
  mode?: 'general' | 'local' | 'market_impact'
  location?: string | null
  output?: 'text' | 'audio' | 'both'
  max_tool_calls?: number
}

export type AssistantRun = {
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

export type ConversationEntry = {
  id: string
  conversation_id: string
  role: string
  content: string
  metadata_json: Record<string, unknown>
  created_at: string
}

export type NewsSource = {
  id: string
  title: string
  url: string
  domain?: string
  published_at?: string | null
}

export type NewsBrief = {
  task_id: string
  status: string
  query: string
  mode: string
  output: string
  voice: string
  audio_available: boolean
  artifact?: {
    id: string
    title: string
    content: {
      summary?: string
      market_impact?: {
        score?: number
        level?: string
        direction?: string
        rationale?: string
      } | null
      sources?: NewsSource[]
      model_warning?: string | null
    }
  } | null
}

export type ResearchRun = {
  task_id: string
  project_id: string
  status: string
  query: string
  artifact?: {
    id: string
    title: string
    content: {
      report?: {
        answer?: string
        findings?: Array<{ claim: string; evidence_invocation_ids: string[] }>
        caveats?: string[]
      }
      tool_results?: Array<{
        slot?: number
        tool_key?: string
        invocation_id?: string
        result?: Record<string, unknown>
      }>
      tool_call_count?: number
    }
  } | null
}

const TERMINAL = new Set(['completed', 'failed'])

export function useAssistant() {
  const [command, setCommand] = useState('')
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ConversationEntry[]>([])
  const [pendingCommandId, setPendingCommandId] = useState<string | null>(null)
  const [lastRoute, setLastRoute] = useState<AssistantRun | null>(null)
  const [activeCapability, setActiveCapability] = useState<string | null>(null)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [brief, setBrief] = useState<NewsBrief | null>(null)
  const [research, setResearch] = useState<ResearchRun | null>(null)
  const [routing, setRouting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)

  function clearResult() {
    setBrief(null)
    setResearch(null)
    setTaskId(null)
    setActiveCapability(null)
  }

  async function sendCommand(textOverride?: string) {
    const text = (textOverride ?? command).trim()
    if (!text) return
    setCommand(text)
    setRouting(true)
    setPendingCommandId(null)
    setError(null)
    clearResult()
    setLastRoute(null)
    try {
      const run = await apiJson<AssistantRun>('/v1/assistant/commands', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          conversation_id: conversationId,
          locale: 'fr-FR',
          output: 'auto',
        }),
      })
      setLastRoute(run)
      setConversationId(run.conversation_id)
      if (run.status === 'routing' && run.routing === 'semantic') {
        setPendingCommandId(run.command_id)
        return
      }
      if (!run.task_id || !run.capability) {
        throw new Error('KAIRO a accepté la commande sans fournir de capacité finale.')
      }
      setActiveCapability(run.capability)
      setTaskId(run.task_id)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Impossible de router la commande.')
    } finally {
      setRouting(false)
    }
  }

  useEffect(() => {
    if (!pendingCommandId) return
    let cancelled = false
    let timer: number | undefined

    const poll = async () => {
      try {
        const state = await apiJson<CommandState>(`/v1/commands/${pendingCommandId}`)
        if (cancelled) return
        if (state.status === 'accepted' && state.task_id && state.capability_key) {
          setLastRoute({
            command_id: state.id,
            conversation_id: state.conversation_id,
            status: state.status,
            routing: 'semantic',
            capability: state.capability_key,
            confidence: state.confidence == null ? null : Number(state.confidence),
            route_reason: state.route_reason || 'semantic.model',
            parameters: state.parameters_json || {},
            task_id: state.task_id,
          })
          setActiveCapability(state.capability_key)
          setTaskId(state.task_id)
          setPendingCommandId(null)
          return
        }
        if (state.status === 'unsupported') {
          setPendingCommandId(null)
          setError('KAIRO ne dispose pas encore d’une capacité sûre pour cette demande.')
          return
        }
        if (state.status === 'failed') {
          setPendingCommandId(null)
          setError('Le routage sémantique KAIRO a échoué. Aucune action n’a été exécutée.')
          return
        }
        timer = window.setTimeout(poll, 700)
      } catch (cause) {
        if (!cancelled) {
          setPendingCommandId(null)
          setError(cause instanceof Error ? cause.message : 'Impossible de suivre le routage.')
        }
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [pendingCommandId])

  useEffect(() => {
    if (!taskId || !activeCapability) return
    let cancelled = false
    let timer: number | undefined

    const poll = async () => {
      try {
        if (activeCapability === 'news.brief') {
          const data = await apiJson<NewsBrief>(`/v1/news/briefs/${taskId}`)
          if (cancelled) return
          setBrief(data)
          if (!TERMINAL.has(data.status)) timer = window.setTimeout(poll, 1200)
          return
        }
        if (activeCapability === 'research.autonomous') {
          const data = await apiJson<ResearchRun>(`/v1/research/runs/${taskId}`)
          if (cancelled) return
          setResearch(data)
          if (!TERMINAL.has(data.status)) timer = window.setTimeout(poll, 1200)
          return
        }
        setError(`La vue KAIRO ne sait pas encore afficher la capacité ${activeCapability}.`)
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : 'Impossible de lire la tâche.')
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [activeCapability, taskId])

  useEffect(() => {
    if (!conversationId) {
      setMessages([])
      return
    }
    let cancelled = false
    const refresh = async () => {
      try {
        const entries = await apiJson<ConversationEntry[]>(`/v1/conversations/${conversationId}/messages`)
        if (!cancelled) setMessages(entries)
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : 'Impossible de relire la conversation.')
      }
    }
    void refresh()
    return () => {
      cancelled = true
    }
  }, [brief?.status, conversationId, pendingCommandId, research?.status, taskId])

  useEffect(() => {
    if (!brief?.audio_available || !brief.task_id) {
      setAudioUrl(null)
      return
    }

    let cancelled = false
    let objectUrl: string | null = null
    const load = async () => {
      try {
        const response = await authenticatedFetch(
          `${API_URL}/v1/news/briefs/${brief.task_id}/audio?voice=${encodeURIComponent(brief.voice)}`,
          { headers: { Accept: 'audio/*' } },
        )
        if (!response.ok) return
        const blob = await response.blob()
        objectUrl = URL.createObjectURL(blob)
        if (cancelled) {
          URL.revokeObjectURL(objectUrl)
          objectUrl = null
          return
        }
        setAudioUrl(objectUrl)
      } catch {
        if (!cancelled) setAudioUrl(null)
      }
    }

    setAudioUrl(null)
    void load()
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [brief?.audio_available, brief?.task_id, brief?.voice])

  const status = brief?.status || research?.status || (pendingCommandId ? 'routing' : taskId ? 'running' : 'idle')
  const busy = routing || pendingCommandId !== null || (status !== 'idle' && !TERMINAL.has(status))
  const sources = useMemo(() => brief?.artifact?.content.sources || [], [brief])

  return {
    command,
    setCommand,
    sendCommand,
    conversationId,
    messages,
    pendingCommandId,
    lastRoute,
    activeCapability,
    taskId,
    brief,
    research,
    sources,
    status,
    busy,
    error,
    clearError: () => setError(null),
    audioUrl,
  }
}

export type AssistantController = ReturnType<typeof useAssistant>
