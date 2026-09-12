import type { FormEventHandler } from 'react'

export type CommandRouteSummary = {
  capability?: string | null
  routing: 'deterministic' | 'semantic'
  confidence?: number | null
  route_reason: string
}

export type CommandTaskSummary = {
  capability: string
  status: string
  title?: string | null
  answer?: string | null
  artifact?: {
    title: string
    kind: string
  } | null
}

type CommandCenterPanelProps = {
  command: string
  conversationId: string | null
  pendingCommandId: string | null
  routing: boolean
  route: CommandRouteSummary | null
  task: CommandTaskSummary | null
  error: string | null
  onCommandChange: (value: string) => void
  onSubmit: FormEventHandler<HTMLFormElement>
  onUseExample: (value: string) => void
}

const EXAMPLES = [
  ['Nouvelles de Paris', 'Quelles sont les nouvelles du jour sur la ville de Paris ?'],
  ['Routage sémantique', "Que s'est-il passé à Paris ce matin ?"],
  ['Impact bourse', "Quelles sont les nouvelles qui risquent d'impacter la bourse aujourd'hui ?"],
  ['Briefing oral', "Lis-moi les nouvelles qui risquent d'impacter les marchés aujourd'hui."],
] as const

export default function CommandCenterPanel({
  command,
  conversationId,
  pendingCommandId,
  routing,
  route,
  task,
  error,
  onCommandChange,
  onSubmit,
  onUseExample,
}: CommandCenterPanelProps) {
  const routeConfidence = route?.confidence == null ? null : Math.round(route.confidence * 100)

  return (
    <section className="command-center" aria-labelledby="command-heading">
      <div>
        <span className="eyebrow">Nevolium COMMAND</span>
        <h2 id="command-heading">Demande directement. Nevolium choisit la capacité.</h2>
      </div>

      <form className="command-form" onSubmit={onSubmit}>
        <input
          value={command}
          onChange={(event) => onCommandChange(event.target.value)}
          minLength={2}
          placeholder="Ex. Que s’est-il passé à Paris ce matin ?"
          aria-label="Commande Nevolium"
        />
        <button type="submit" disabled={routing || pendingCommandId !== null || !command.trim()}>
          {routing ? 'Routage…' : pendingCommandId ? 'Analyse sémantique…' : 'Demander à Nevolium'}
        </button>
      </form>

      <div className="command-examples" aria-label="Exemples de commandes">
        {EXAMPLES.map(([label, value]) => (
          <button key={label} type="button" onClick={() => onUseExample(value)}>
            {label}
          </button>
        ))}
      </div>

      {route && (
        <div className="route-chip">
          <span>{route.capability || (route.routing === 'semantic' ? 'analyse sémantique' : 'routage')}</span>
          <small>
            {routeConfidence == null ? '' : `${routeConfidence}% · `}
            {route.route_reason}
          </small>
        </div>
      )}

      {conversationId && (
        <small className="conversation-chip">
          conversation {conversationId.slice(0, 8)}… persistée côté serveur
        </small>
      )}

      {error && <div className="error-panel">{error}</div>}

      {pendingCommandId && !error && (
        <div className="progress-panel">
          <strong>Nevolium interprète la demande via une capacité de routage durable.</strong>
          <span>Le modèle ne peut proposer qu’une capacité enregistrée ; Core valide avant toute exécution.</span>
        </div>
      )}

      {task && task.capability !== 'news.brief' && !error && (
        <div className="progress-panel">
          <strong>{task.answer || task.title || `${task.capability} · ${task.status}`}</strong>
          <span>
            {task.answer
              ? `${task.capability} · ${task.status}`
              : task.artifact
                ? `${task.artifact.title} · ${task.artifact.kind}`
                : `Tâche durable Nevolium · ${task.status}`}
          </span>
        </div>
      )}
    </section>
  )
}
