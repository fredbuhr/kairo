import { FormEvent, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { KairoGraphEntityRef } from '@kairo/graph'

import type { ProjectRecord } from '../../lib/api'
import {
  createAutomation,
  fetchAutomationRuns,
  fetchAutomations,
  fetchSecretReferences,
  invokeAutomation,
  updateAutomation,
  type AutomationRecord,
  type AutomationRunRecord,
  type SecretReferenceRecord,
} from '../../lib/automationApi'

function shortDateTime(value?: string | null) {
  if (!value) return '—'
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))
  } catch {
    return value
  }
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    pending: 'En attente',
    queued: 'Planifiée',
    running: 'En cours',
    completed: 'Terminée',
    failed: 'Échec',
    cancelled: 'Annulée',
  }
  return labels[value] || value
}

function AutomationCreateForm({
  projects,
  secretReferences,
}: {
  projects: ProjectRecord[]
  secretReferences: SecretReferenceRecord[]
}) {
  const client = useQueryClient()
  const [projectId, setProjectId] = useState(projects.find((project) => project.status !== 'archived')?.id || '')
  const [key, setKey] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [secretReferenceId, setSecretReferenceId] = useState(secretReferences[0]?.id || '')
  const [secretKey, setSecretKey] = useState('path')
  const [authorityLevel, setAuthorityLevel] = useState(2)
  const [timeoutSeconds, setTimeoutSeconds] = useState(60)

  const mutation = useMutation({
    mutationFn: () => createAutomation({
      project_id: projectId,
      key: key.trim(),
      name: name.trim(),
      description: description.trim() || null,
      authority_level: authorityLevel,
      webhook_secret_reference_id: secretReferenceId,
      webhook_secret_key: secretKey.trim() || 'path',
      timeout_seconds: timeoutSeconds,
    }),
    onSuccess: async () => {
      setKey('')
      setName('')
      setDescription('')
      await Promise.all([
        client.invalidateQueries({ queryKey: ['automations'] }),
        client.invalidateQueries({ queryKey: ['agent-executions'] }),
      ])
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!projectId || !key.trim() || !name.trim() || !secretReferenceId || mutation.isPending) return
    mutation.mutate()
  }

  return (
    <form className="workspace-create automation-create" onSubmit={submit}>
      <div className="workspace-create-heading">
        <div><span className="kairo-kicker">NOUVELLE</span><strong>Automation KAIRO</strong></div>
        <button type="submit" disabled={!projectId || !key.trim() || !name.trim() || !secretReferenceId || mutation.isPending}>{mutation.isPending ? 'Création…' : 'Créer'}</button>
      </div>
      <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
        <option value="">Choisir un projet</option>
        {projects.filter((project) => project.status !== 'archived').map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
      </select>
      <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Nom affiché" maxLength={240} />
      <input value={key} onChange={(event) => setKey(event.target.value.toLowerCase())} placeholder="clé-automation" maxLength={160} />
      <textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description optionnelle" rows={2} />
      <label><span>Référence OpenBao</span><select value={secretReferenceId} onChange={(event) => setSecretReferenceId(event.target.value)}><option value="">Choisir une référence</option>{secretReferences.map((reference) => <option key={reference.id} value={reference.id}>{reference.name} · {reference.purpose}</option>)}</select></label>
      <label><span>Champ secret contenant le chemin webhook</span><input value={secretKey} onChange={(event) => setSecretKey(event.target.value)} placeholder="path" maxLength={120} /></label>
      <label><span>Autorité</span><select value={authorityLevel} onChange={(event) => setAuthorityLevel(Number(event.target.value))}><option value={1}>A1 · faible</option><option value={2}>A2 · écriture externe</option><option value={3}>A3 · sensible</option></select></label>
      <label><span>Timeout</span><select value={timeoutSeconds} onChange={(event) => setTimeoutSeconds(Number(event.target.value))}><option value={30}>30 s</option><option value={60}>60 s</option><option value={120}>120 s</option><option value={300}>300 s</option></select></label>
      <small className="automation-secret-note">La référence stocke seulement un pointeur OpenBao. La valeur secrète doit contenir le chemin du webhook Activepieces, jamais l’URL d’un autre hôte. Une automation neuve reste désactivée.</small>
      {secretReferences.length === 0 && <small className="workspace-error">Aucune référence OpenBao n’est disponible. Créez/provisionnez d’abord une SecretReference.</small>}
      {mutation.isError && <small className="workspace-error">{mutation.error instanceof Error ? mutation.error.message : 'Création impossible.'}</small>}
    </form>
  )
}

function RunComposer({ automation }: { automation: AutomationRecord }) {
  const client = useQueryClient()
  const [payload, setPayload] = useState('{}')
  const [parseError, setParseError] = useState('')
  const mutation = useMutation({
    mutationFn: () => {
      let parsed: unknown
      try {
        parsed = JSON.parse(payload || '{}')
      } catch {
        throw new Error('Le JSON d’entrée est invalide.')
      }
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('L’entrée doit être un objet JSON.')
      }
      return invokeAutomation(automation.id, parsed as Record<string, unknown>)
    },
    onMutate: () => setParseError(''),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['automation-runs'] }),
        client.invalidateQueries({ queryKey: ['agent-executions'] }),
        client.invalidateQueries({ queryKey: ['kairo-graph'] }),
      ])
    },
    onError: (error) => setParseError(error instanceof Error ? error.message : 'Exécution impossible.'),
  })

  return (
    <section className="automation-run-composer">
      <div><span className="kairo-kicker">EXÉCUTER</span><strong>{automation.name}</strong></div>
      <textarea value={payload} onChange={(event) => setPayload(event.target.value)} rows={8} spellCheck={false} aria-label="Entrée JSON de l’automation" />
      <button type="button" disabled={!automation.enabled || mutation.isPending} onClick={() => mutation.mutate()}>{mutation.isPending ? 'Démarrage…' : automation.enabled ? 'Lancer via KAIRO' : 'Automation désactivée'}</button>
      <small>Le POST webhook est exécuté par Temporal avec un seul essai. Une réponse perdue est enregistrée comme résultat ambigu plutôt que rejouée automatiquement.</small>
      {parseError && <small className="workspace-error">{parseError}</small>}
    </section>
  )
}

function RunRow({
  run,
  automation,
  onExploreEntity,
}: {
  run: AutomationRunRecord
  automation?: AutomationRecord
  onExploreEntity: (entity: KairoGraphEntityRef) => void
}) {
  return (
    <button type="button" className={`automation-run-row automation-run-${run.status}`} onClick={() => onExploreEntity({ entity_type: 'task', entity_id: run.task_id })}>
      <i />
      <div>
        <strong>{automation?.name || 'Automation'}</strong>
        <small>{statusLabel(run.status)} · {shortDateTime(run.created_at)}{run.response_status ? ` · HTTP ${run.response_status}` : ''}</small>
        {run.last_error && <span>{run.last_error}</span>}
      </div>
      <div>
        {run.outcome_ambiguous && <b>AMBIGU</b>}
        <span>Task ↗</span>
      </div>
    </button>
  )
}

export function AutomationsWorkspace({
  projects,
  onExploreEntity,
}: {
  projects: ProjectRecord[]
  onExploreEntity: (entity: KairoGraphEntityRef) => void
}) {
  const client = useQueryClient()
  const automationsQuery = useQuery({
    queryKey: ['automations'],
    queryFn: fetchAutomations,
    staleTime: 5000,
  })
  const runsQuery = useQuery({
    queryKey: ['automation-runs'],
    queryFn: () => fetchAutomationRuns(),
    staleTime: 3000,
    refetchInterval: 5000,
  })
  const secretsQuery = useQuery({
    queryKey: ['secret-references'],
    queryFn: fetchSecretReferences,
    staleTime: 15_000,
  })
  const automations = automationsQuery.data || []
  const runs = runsQuery.data || []
  const secretReferences = secretsQuery.data || []
  const [selectedId, setSelectedId] = useState('')
  const selected = automations.find((automation) => automation.id === selectedId) || automations[0] || null
  const automationById = useMemo(() => new Map(automations.map((automation) => [automation.id, automation])), [automations])
  const projectById = useMemo(() => new Map(projects.map((project) => [project.id, project])), [projects])

  const toggle = useMutation({
    mutationFn: ({ automationId, enabled }: { automationId: string; enabled: boolean }) => updateAutomation(automationId, { enabled }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['automations'] })
    },
  })

  const error = automationsQuery.error || runsQuery.error
  if (automationsQuery.isLoading || runsQuery.isLoading) {
    return <div className="workspace-state"><span className="kairo-kicker">AUTOMATISATIONS</span><strong>Lecture du registre KAIRO…</strong></div>
  }
  if (error) {
    return <div className="workspace-state workspace-state-error"><strong>Impossible de lire les automatisations.</strong><span>{error instanceof Error ? error.message : 'Erreur KAIRO Core.'}</span></div>
  }

  return (
    <div className="automations-workspace">
      <section className="automations-main">
        <header className="workspace-title">
          <div><span className="kairo-kicker">AUTOMATISATIONS</span><h1>Orchestration KAIRO</h1><p>KAIRO reste l’autorité : définition, policy, audit, Task et résultat. Activepieces fournit le moteur spécialiste derrière un webhook secret, sans devenir une seconde application de référence.</p></div>
          <strong>{automations.filter((automation) => automation.enabled).length}/{automations.length}</strong>
        </header>

        {automations.length === 0 ? (
          <div className="workspace-empty"><strong>Aucune automation enregistrée.</strong><span>Créez une définition KAIRO reliée à un webhook Activepieces déjà provisionné dans OpenBao.</span></div>
        ) : (
          <div className="automation-grid">
            {automations.map((automation) => (
              <article key={automation.id} className={`automation-card ${automation.enabled ? 'automation-card-enabled' : ''} ${selected?.id === automation.id ? 'automation-card-selected' : ''}`} onClick={() => setSelectedId(automation.id)}>
                <div className="automation-card-top"><i className={automation.enabled ? 'automation-live' : ''} /><span>{automation.enabled ? 'Autorisée' : 'Désactivée'}</span><small>A{automation.authority_level}</small></div>
                <h2>{automation.name}</h2>
                <p>{automation.description || 'Aucune description.'}</p>
                <div className="automation-meta"><span>{projectById.get(automation.project_id)?.name || 'Projet'}</span><span>{automation.engine}</span><span>{automation.timeout_seconds}s</span></div>
                <div className="automation-card-actions">
                  <button type="button" disabled={toggle.isPending} onClick={(event) => { event.stopPropagation(); toggle.mutate({ automationId: automation.id, enabled: !automation.enabled }) }}>{automation.enabled ? 'Désactiver' : 'Activer'}</button>
                  <button type="button" onClick={(event) => { event.stopPropagation(); setSelectedId(automation.id) }}>Inspecter</button>
                </div>
              </article>
            ))}
          </div>
        )}
        {toggle.isError && <small className="workspace-error automation-global-error">{toggle.error instanceof Error ? toggle.error.message : 'Politique impossible.'}</small>}

        <section className="automation-runs">
          <header><div><span className="kairo-kicker">EXÉCUTIONS</span><strong>Derniers passages</strong></div><b>{runs.length}</b></header>
          {runs.length === 0 ? <div className="workspace-empty"><strong>Aucune exécution.</strong></div> : runs.map((run) => <RunRow key={run.id} run={run} automation={automationById.get(run.automation_id)} onExploreEntity={onExploreEntity} />)}
        </section>
      </section>

      <aside className="automations-side">
        {selected && <RunComposer automation={selected} />}
        <AutomationCreateForm projects={projects} secretReferences={secretReferences} />
        {secretsQuery.isError && <small className="workspace-error">Les références OpenBao ne peuvent pas être lues avec l’identité actuelle.</small>}
      </aside>
    </div>
  )
}
