import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createSecretReference,
  fetchSecretReferences,
  fetchSecretReferenceStatus,
  provisionSecretReference,
} from '../../lib/automationApi'

type SecretField = { id: number; key: string; value: string }

function starterFields(purpose: string): SecretField[] {
  if (purpose === 'rotki') {
    return [
      { id: 1, key: 'username', value: '' },
      { id: 2, key: 'password', value: '' },
    ]
  }
  if (purpose === 'activepieces') return [{ id: 1, key: 'path', value: '' }]
  return [{ id: 1, key: '', value: '' }]
}

export function SecretVaultSettings() {
  const client = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [purpose, setPurpose] = useState('rotki')
  const [selectedId, setSelectedId] = useState('')
  const [fields, setFields] = useState<SecretField[]>(() => starterFields('rotki'))
  const [nextFieldId, setNextFieldId] = useState(3)

  const referencesQuery = useQuery({
    queryKey: ['secret-references'],
    queryFn: fetchSecretReferences,
    staleTime: 20_000,
  })
  const references = referencesQuery.data || []
  const selected = references.find((reference) => reference.id === selectedId) || null
  const statusQuery = useQuery({
    queryKey: ['secret-reference-status', selectedId],
    queryFn: () => fetchSecretReferenceStatus(selectedId),
    enabled: Boolean(selectedId),
    staleTime: 5000,
    retry: false,
  })

  useEffect(() => {
    if (!selectedId && references.length > 0) setSelectedId(references[0].id)
    if (selectedId && !references.some((reference) => reference.id === selectedId)) {
      setSelectedId(references[0]?.id || '')
    }
  }, [references, selectedId])

  useEffect(() => {
    setFields(starterFields(purpose))
    setNextFieldId(purpose === 'rotki' ? 3 : 2)
  }, [purpose])

  const createMutation = useMutation({
    mutationFn: () => createSecretReference(
      name.trim(),
      purpose === 'rotki'
        ? 'Identifiants Rotki'
        : purpose === 'activepieces'
          ? 'Webhook Activepieces'
          : 'Secret KAIRO',
    ),
    onSuccess: async (reference) => {
      setName('')
      setCreating(false)
      setSelectedId(reference.id)
      await client.invalidateQueries({ queryKey: ['secret-references'] })
    },
  })

  const values = useMemo(() => {
    const result: Record<string, string> = {}
    for (const field of fields) {
      const key = field.key.trim()
      if (key && field.value) result[key] = field.value
    }
    return result
  }, [fields])

  const provisionMutation = useMutation({
    mutationFn: () => provisionSecretReference(selectedId, values),
    onSuccess: async () => {
      setFields((current) => current.map((field) => ({ ...field, value: '' })))
      await client.invalidateQueries({ queryKey: ['secret-reference-status', selectedId] })
    },
  })

  function create(event: FormEvent) {
    event.preventDefault()
    if (!name.trim() || createMutation.isPending) return
    createMutation.mutate()
  }

  function provision(event: FormEvent) {
    event.preventDefault()
    if (!selectedId || Object.keys(values).length === 0 || provisionMutation.isPending) return
    provisionMutation.mutate()
  }

  function updateField(id: number, patch: Partial<Pick<SecretField, 'key' | 'value'>>) {
    setFields((current) => current.map((field) => field.id === id ? { ...field, ...patch } : field))
  }

  return (
    <section className="secret-vault-settings">
      <header>
        <div>
          <span className="kairo-kicker">COFFRE PERSONNEL</span>
          <strong>Connexions & secrets</strong>
        </div>
        <button type="button" onClick={() => setCreating((value) => !value)}>{creating ? 'Fermer' : '+ Référence'}</button>
      </header>
      <p>
        Les valeurs sont écrites directement dans OpenBao et ne sont jamais relues dans cette interface.
        KAIRO conserve uniquement une référence, les noms de champs et la version du secret.
      </p>

      {creating && (
        <form className="secret-vault-create" onSubmit={create}>
          <label>
            <span>Usage</span>
            <select value={purpose} onChange={(event) => setPurpose(event.target.value)}>
              <option value="rotki">Rotki</option>
              <option value="activepieces">Activepieces</option>
              <option value="custom">Personnalisé</option>
            </select>
          </label>
          <label><span>Nom</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Mon compte principal" /></label>
          <button type="submit" disabled={!name.trim() || createMutation.isPending}>{createMutation.isPending ? 'Création…' : 'Créer le coffre'}</button>
          {createMutation.isError && <small className="workspace-error">{createMutation.error instanceof Error ? createMutation.error.message : 'Création impossible.'}</small>}
        </form>
      )}

      {referencesQuery.isLoading ? (
        <span className="secret-vault-muted">Lecture des références…</span>
      ) : references.length === 0 ? (
        <div className="secret-vault-empty"><strong>Aucun secret configuré.</strong><span>Créez une référence avant de connecter Rotki ou une automation.</span></div>
      ) : (
        <>
          <label className="secret-vault-selector">
            <span>Référence</span>
            <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
              {references.map((reference) => <option key={reference.id} value={reference.id}>{reference.name} · {reference.purpose}</option>)}
            </select>
          </label>

          {selected && (
            <div className="secret-vault-status">
              <div><span>État</span><strong>{statusQuery.data?.exists ? 'Provisionné' : statusQuery.isLoading ? 'Vérification…' : 'Vide'}</strong></div>
              <div><span>Champs connus</span><strong>{statusQuery.data?.keys.length ? statusQuery.data.keys.join(', ') : '—'}</strong></div>
              <div><span>Version</span><strong>{statusQuery.data?.version ?? '—'}</strong></div>
            </div>
          )}

          <form className="secret-vault-values" onSubmit={provision} autoComplete="off">
            <div className="secret-vault-values-head">
              <strong>Écrire / remplacer les valeurs</strong>
              <small>Les champs saisis quittent la mémoire du formulaire après l’enregistrement.</small>
            </div>
            {fields.map((field) => (
              <div className="secret-vault-field" key={field.id}>
                <input
                  aria-label="Nom du champ secret"
                  value={field.key}
                  onChange={(event) => updateField(field.id, { key: event.target.value })}
                  placeholder="champ"
                  autoComplete="off"
                />
                <input
                  aria-label={`Valeur secrète ${field.key || ''}`}
                  type="password"
                  value={field.value}
                  onChange={(event) => updateField(field.id, { value: event.target.value })}
                  placeholder="Valeur non affichée"
                  autoComplete="new-password"
                />
                <button type="button" aria-label="Retirer le champ" disabled={fields.length === 1} onClick={() => setFields((current) => current.filter((item) => item.id !== field.id))}>×</button>
              </div>
            ))}
            <div className="secret-vault-value-actions">
              <button type="button" onClick={() => { setFields((current) => [...current, { id: nextFieldId, key: '', value: '' }]); setNextFieldId((value) => value + 1) }}>+ Champ</button>
              <button type="submit" disabled={!selectedId || Object.keys(values).length === 0 || provisionMutation.isPending}>{provisionMutation.isPending ? 'Écriture…' : 'Enregistrer dans OpenBao'}</button>
            </div>
            {provisionMutation.isError && <small className="workspace-error">{provisionMutation.error instanceof Error ? provisionMutation.error.message : 'Écriture impossible.'}</small>}
          </form>
        </>
      )}
    </section>
  )
}
