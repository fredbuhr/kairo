import type { AssistantController, ConversationEntry } from './useAssistant'

function shortId(value?: string) {
  return value ? `${value.slice(0, 8)}…` : 'preuve'
}

function entryLabel(entry: ConversationEntry) {
  if (entry.role === 'user') return 'Vous'
  if (entry.metadata_json.kind === 'capability-failure') return 'KAIRO · échec'
  const capability = entry.metadata_json.capability
  return typeof capability === 'string' && capability ? `KAIRO · ${capability}` : 'KAIRO'
}

export function AssistantDrawer({
  assistant,
  open,
  onClose,
}: {
  assistant: AssistantController
  open: boolean
  onClose: () => void
}) {
  const report = assistant.research?.artifact?.content.report
  const findings = report?.findings || []
  const caveats = report?.caveats || []
  const toolResults = assistant.research?.artifact?.content.tool_results || []
  const impact = assistant.brief?.artifact?.content.market_impact

  return (
    <aside className={`assistant-drawer ${open ? 'assistant-drawer-open' : ''}`} aria-hidden={!open}>
      <header className="assistant-drawer-header">
        <div>
          <span className="kairo-kicker">KAIRO</span>
          <strong>Conversation</strong>
        </div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Fermer la conversation">×</button>
      </header>

      <div className="assistant-scroll">
        {assistant.messages.length === 0 && !assistant.busy && (
          <div className="assistant-empty">
            <span className="kairo-orb-small" aria-hidden="true" />
            <p>Demandez quelque chose à KAIRO. Le langage naturel complète la navigation spatiale, sans la remplacer.</p>
          </div>
        )}

        {assistant.messages.map((entry) => (
          <article key={entry.id} className={`assistant-message assistant-message-${entry.role === 'assistant' ? 'assistant' : 'user'}`}>
            <small>{entryLabel(entry)}</small>
            <p>{entry.content}</p>
            {entry.role === 'assistant' && typeof entry.metadata_json.artifact_id === 'string' && (
              <span>artefact · {shortId(entry.metadata_json.artifact_id)}</span>
            )}
          </article>
        ))}

        {assistant.busy && (
          <div className="assistant-working" role="status">
            <span className="working-dot" />
            <div>
              <strong>{assistant.pendingCommandId ? 'KAIRO interprète la demande' : 'KAIRO travaille'}</strong>
              <small>Exécution durable, contrôlée par KAIRO Core.</small>
            </div>
          </div>
        )}

        {assistant.error && (
          <div className="assistant-error">
            <span>{assistant.error}</span>
            <button type="button" onClick={assistant.clearError}>Fermer</button>
          </div>
        )}

        {assistant.brief?.artifact && (
          <section className="capability-result">
            <header>
              <span className="kairo-kicker">NEWS INTELLIGENCE</span>
              <h3>{assistant.brief.artifact.title}</h3>
            </header>
            {impact && (
              <div className="result-metric">
                <strong>{Math.round(impact.score || 0)}</strong>
                <span>/100 · impact {impact.level || 'non évalué'}</span>
              </div>
            )}
            {impact?.rationale && <p className="result-note">{impact.rationale}</p>}
            {assistant.brief.output !== 'audio' && <p className="result-body">{assistant.brief.artifact.content.summary}</p>}
            {assistant.audioUrl && (
              <audio controls preload="none" src={assistant.audioUrl} className="assistant-audio" />
            )}
            {assistant.brief.artifact.content.model_warning && (
              <p className="result-warning">{assistant.brief.artifact.content.model_warning}</p>
            )}
            {assistant.sources.length > 0 && (
              <div className="result-sources">
                <span>Sources</span>
                {assistant.sources.map((source) => (
                  <a key={source.id} href={source.url} target="_blank" rel="noreferrer">
                    <strong>{source.title}</strong>
                    <small>{source.domain || 'source'}{source.published_at ? ` · ${source.published_at}` : ''}</small>
                  </a>
                ))}
              </div>
            )}
          </section>
        )}

        {assistant.research?.artifact && (
          <section className="capability-result">
            <header>
              <span className="kairo-kicker">RECHERCHE AUTONOME</span>
              <h3>{assistant.research.artifact.title}</h3>
            </header>
            <p className="result-body">{report?.answer}</p>
            {findings.length > 0 && (
              <div className="result-findings">
                <span>Conclusions vérifiables</span>
                {findings.map((finding, index) => (
                  <article key={`${finding.claim}-${index}`}>
                    <strong>{finding.claim}</strong>
                    <small>preuves · {finding.evidence_invocation_ids.map(shortId).join(', ')}</small>
                  </article>
                ))}
              </div>
            )}
            {caveats.length > 0 && (
              <div className="result-caveats">
                <span>Limites</span>
                {caveats.map((caveat) => <p key={caveat}>{caveat}</p>)}
              </div>
            )}
            {toolResults.length > 0 && (
              <div className="result-tools">
                <span>Outils MCP exécutés</span>
                {toolResults.map((tool, index) => (
                  <div key={tool.invocation_id || `${tool.tool_key}-${index}`}>
                    <strong>{tool.tool_key || 'outil MCP'}</strong>
                    <small>{shortId(tool.invocation_id)}</small>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </aside>
  )
}
