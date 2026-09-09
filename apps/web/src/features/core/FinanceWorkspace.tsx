import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { ProjectRecord } from '../../lib/api'
import {
  createFinanceTransactionProposal,
  fetchFinancePortfolio,
  fetchFinanceTransactionProposals,
  type FinanceAccountRecord,
  type FinancePositionRecord,
} from '../../lib/financeApi'

function numberValue(value?: string | number | null) {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function money(value?: string | number | null) {
  const parsed = numberValue(value)
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: Math.abs(parsed) < 1 ? 4 : 2,
  }).format(parsed)
}

function quantity(value: string | number) {
  const parsed = numberValue(value)
  return new Intl.NumberFormat('fr-FR', {
    maximumFractionDigits: Math.abs(parsed) < 1 ? 8 : 4,
  }).format(parsed)
}

function shortDateTime(value?: string | null) {
  if (!value) return 'Jamais'
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

function shortAddress(value?: string | null) {
  if (!value) return '—'
  if (value.length <= 18) return value
  return `${value.slice(0, 8)}…${value.slice(-6)}`
}

function proposalStatus(value: string) {
  const labels: Record<string, string> = {
    draft: 'Brouillon',
    cancelled: 'Annulée',
    signed: 'Signée',
    submitted: 'Soumise',
  }
  return labels[value] || value
}

function PositionRow({
  position,
  allocation,
}: {
  position: FinancePositionRecord
  allocation: number
}) {
  const pnl = position.unrealized_pnl_usd == null ? null : numberValue(position.unrealized_pnl_usd)
  return (
    <article className="finance-position-row">
      <div className="finance-asset-mark"><strong>{position.symbol.slice(0, 4)}</strong></div>
      <div className="finance-position-identity">
        <strong>{position.symbol}</strong>
        <span>{position.name || position.asset_key}</span>
        <small>{position.account_label} · {position.network || position.account_type}</small>
      </div>
      <div className="finance-position-quantity">
        <strong>{quantity(position.quantity)}</strong>
        <span>{position.unit_price_usd == null ? 'prix non fourni' : money(position.unit_price_usd)}</span>
      </div>
      <div className="finance-position-value">
        <strong>{money(position.value_usd)}</strong>
        <span className={pnl == null ? '' : pnl >= 0 ? 'finance-positive' : 'finance-negative'}>
          {pnl == null ? 'P/L indisponible' : `${pnl >= 0 ? '+' : ''}${money(pnl)}`}
        </span>
      </div>
      <div className="finance-allocation" title={`${allocation.toFixed(1)} % du portefeuille positif`}>
        <i style={{ width: `${Math.max(0, Math.min(100, allocation))}%` }} />
      </div>
    </article>
  )
}

function AccountCard({ account, positions }: { account: FinanceAccountRecord; positions: FinancePositionRecord[] }) {
  const value = positions.reduce((sum, position) => sum + numberValue(position.value_usd), 0)
  return (
    <article className="finance-account-card">
      <header>
        <div><strong>{account.label}</strong><span>{account.account_type}</span></div>
        <b>{money(value)}</b>
      </header>
      <dl>
        <div><dt>Réseau</dt><dd>{account.network || 'multi-réseaux'}</dd></div>
        <div><dt>Adresse publique</dt><dd title={account.public_address || undefined}>{shortAddress(account.public_address)}</dd></div>
        <div><dt>Positions</dt><dd>{positions.length}</dd></div>
        <div><dt>Observé</dt><dd>{shortDateTime(account.observed_at)}</dd></div>
      </dl>
    </article>
  )
}

function ProposalForm({
  projects,
  accounts,
  positions,
}: {
  projects: ProjectRecord[]
  accounts: FinanceAccountRecord[]
  positions: FinancePositionRecord[]
}) {
  const client = useQueryClient()
  const [projectId, setProjectId] = useState('')
  const [accountId, setAccountId] = useState('')
  const [assetKey, setAssetKey] = useState('')
  const [network, setNetwork] = useState('')
  const [amount, setAmount] = useState('')
  const [destination, setDestination] = useState('')
  const [memo, setMemo] = useState('')

  const account = accounts.find((item) => item.id === accountId) || null
  const accountPositions = useMemo(
    () => positions.filter((position) => position.account_id === accountId),
    [accountId, positions],
  )
  const selectedPosition = accountPositions.find((position) => position.asset_key === assetKey) || null

  useEffect(() => {
    if (!accountId && accounts.length > 0) setAccountId(accounts[0].id)
    if (accountId && !accounts.some((item) => item.id === accountId)) setAccountId(accounts[0]?.id || '')
  }, [accountId, accounts])

  useEffect(() => {
    if (!assetKey || !accountPositions.some((position) => position.asset_key === assetKey)) {
      setAssetKey(accountPositions[0]?.asset_key || '')
    }
  }, [accountPositions, assetKey])

  useEffect(() => {
    setNetwork(account?.network || selectedPosition?.network || '')
  }, [account?.network, selectedPosition?.network])

  const mutation = useMutation({
    mutationFn: () => {
      if (!account || !selectedPosition) throw new Error('Sélectionnez un compte et un actif observé.')
      return createFinanceTransactionProposal({
        project_id: projectId || null,
        from_account_id: account.id,
        network: network.trim(),
        asset_key: selectedPosition.asset_key,
        symbol: selectedPosition.symbol,
        amount: amount.trim(),
        destination: destination.trim(),
        memo: memo.trim() || null,
        simulation: {
          source: 'cockpit-draft',
          portfolio_observed_at: selectedPosition.observed_at,
        },
      })
    },
    onSuccess: async () => {
      setAmount('')
      setDestination('')
      setMemo('')
      await client.invalidateQueries({ queryKey: ['finance-proposals'] })
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    const parsed = Number(amount)
    if (!account || !selectedPosition || !network.trim() || !destination.trim() || !Number.isFinite(parsed) || parsed <= 0 || mutation.isPending) return
    mutation.mutate()
  }

  return (
    <form className="finance-proposal-form" onSubmit={submit}>
      <header>
        <div><span className="kairo-kicker">TRANSACTION</span><strong>Préparer un transfert</strong></div>
        <b>BROUILLON</b>
      </header>
      <p className="finance-signing-note">KAIRO prépare et simule. Aucune clé privée, seed phrase ou signature n’entre dans ce processus. La signature restera dans un signer isolé ou votre wallet.</p>
      <label><span>Compte source</span><select value={accountId} onChange={(event) => setAccountId(event.target.value)}><option value="">Choisir…</option>{accounts.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
      <label><span>Actif</span><select value={assetKey} onChange={(event) => setAssetKey(event.target.value)}><option value="">Choisir…</option>{accountPositions.map((position) => <option key={position.id} value={position.asset_key}>{position.symbol} · {quantity(position.quantity)} disponible observé</option>)}</select></label>
      <label><span>Réseau</span><input value={network} onChange={(event) => setNetwork(event.target.value)} placeholder="ethereum" /></label>
      <label><span>Montant</span><input value={amount} onChange={(event) => setAmount(event.target.value)} inputMode="decimal" placeholder="0.0" /></label>
      <label><span>Destination publique</span><input value={destination} onChange={(event) => setDestination(event.target.value)} placeholder="Adresse publique" /></label>
      <label><span>Projet KAIRO (optionnel)</span><select value={projectId} onChange={(event) => setProjectId(event.target.value)}><option value="">Aucun</option>{projects.filter((project) => project.status !== 'archived').map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
      <label><span>Mémo (optionnel)</span><textarea value={memo} onChange={(event) => setMemo(event.target.value)} rows={2} /></label>
      <button type="submit" disabled={mutation.isPending || !account || !selectedPosition || !network.trim() || !amount.trim() || !destination.trim()}>{mutation.isPending ? 'Préparation…' : 'Créer le brouillon'}</button>
      {mutation.isError && <small className="workspace-error">{mutation.error instanceof Error ? mutation.error.message : 'Brouillon impossible.'}</small>}
    </form>
  )
}

export function FinanceWorkspace({ projects }: { projects: ProjectRecord[] }) {
  const [sourceFilter, setSourceFilter] = useState('')
  const portfolioQuery = useQuery({
    queryKey: ['finance-portfolio'],
    queryFn: () => fetchFinancePortfolio(),
    staleTime: 20_000,
    refetchInterval: 60_000,
  })
  const proposalsQuery = useQuery({
    queryKey: ['finance-proposals'],
    queryFn: fetchFinanceTransactionProposals,
    staleTime: 10_000,
  })

  const portfolio = portfolioQuery.data
  const sources = portfolio?.sources || []
  const accounts = useMemo(
    () => (portfolio?.accounts || []).filter((account) => !sourceFilter || account.source_id === sourceFilter),
    [portfolio?.accounts, sourceFilter],
  )
  const positions = useMemo(
    () => (portfolio?.positions || []).filter((position) => !sourceFilter || position.source_id === sourceFilter),
    [portfolio?.positions, sourceFilter],
  )
  const filteredTotal = positions.reduce((sum, position) => sum + numberValue(position.value_usd), 0)
  const positiveTotal = positions.reduce((sum, position) => sum + Math.max(0, numberValue(position.value_usd)), 0)
  const filteredPnl = positions.reduce((sum, position) => sum + numberValue(position.unrealized_pnl_usd), 0)
  const hasPnl = positions.some((position) => position.unrealized_pnl_usd != null)
  const error = portfolioQuery.error || proposalsQuery.error

  if (portfolioQuery.isLoading) {
    return <div className="workspace-state"><span className="kairo-kicker">FINANCE & CRYPTO</span><strong>Lecture du portefeuille sourcé…</strong></div>
  }
  if (error && !portfolio) {
    return <div className="workspace-state workspace-state-error"><strong>Impossible de lire le portefeuille KAIRO.</strong><span>{error instanceof Error ? error.message : 'Erreur KAIRO Core.'}</span></div>
  }

  return (
    <div className="finance-workspace">
      <section className="finance-main">
        <header className="finance-header">
          <div><span className="kairo-kicker">FINANCE & CRYPTO</span><h1>{money(filteredTotal)}</h1><p>Positions observées avec provenance explicite. KAIRO ne transforme jamais une observation de portefeuille en autorité de signature.</p></div>
          <div className="finance-head-metrics"><span><small>Positions</small><strong>{positions.length}</strong></span><span><small>P/L non réalisé</small><strong className={hasPnl ? filteredPnl >= 0 ? 'finance-positive' : 'finance-negative' : ''}>{hasPnl ? `${filteredPnl >= 0 ? '+' : ''}${money(filteredPnl)}` : '—'}</strong></span></div>
        </header>

        <div className="finance-source-strip">
          <button type="button" className={!sourceFilter ? 'finance-source-active' : ''} onClick={() => setSourceFilter('')}>Tout le portefeuille</button>
          {sources.map((source) => <button key={source.id} type="button" className={sourceFilter === source.id ? 'finance-source-active' : ''} onClick={() => setSourceFilter(source.id)}><span>{source.display_name}</span><small>{source.provider} · {shortDateTime(source.last_sync_at)}</small></button>)}
        </div>

        {positions.length === 0 ? (
          <div className="workspace-empty"><strong>Aucune position financière observée.</strong><span>Le Cockpit n’invente pas de portefeuille. Un connecteur Rotki/exchange/wallet alimentera ce read model via la frontière normalisée KAIRO.</span></div>
        ) : (
          <div className="finance-position-list">
            {positions.map((position) => <PositionRow key={position.id} position={position} allocation={positiveTotal > 0 ? Math.max(0, numberValue(position.value_usd)) / positiveTotal * 100 : 0} />)}
          </div>
        )}

        <section className="finance-accounts-section">
          <header><div><span className="kairo-kicker">COMPTES OBSERVÉS</span><strong>Wallets, exchanges et comptes</strong></div><b>{accounts.length}</b></header>
          {accounts.length === 0 ? <div className="workspace-empty"><strong>Aucun compte dans ce filtre.</strong></div> : <div className="finance-account-grid">{accounts.map((account) => <AccountCard key={account.id} account={account} positions={positions.filter((position) => position.account_id === account.id)} />)}</div>}
        </section>
      </section>

      <aside className="finance-side">
        <ProposalForm projects={projects} accounts={accounts} positions={positions} />
        <section className="finance-proposals">
          <header><div><span className="kairo-kicker">PROPOSITIONS</span><strong>Transferts préparés</strong></div><b>{proposalsQuery.data?.length || 0}</b></header>
          {(proposalsQuery.data || []).length === 0 ? <div className="workspace-empty"><strong>Aucun brouillon.</strong><span>Une proposition n’est jamais une transaction signée.</span></div> : (proposalsQuery.data || []).map((proposal) => (
            <article key={proposal.id}>
              <div><strong>{proposal.symbol} · {quantity(proposal.amount)}</strong><span>{proposalStatus(proposal.status)}</span></div>
              <p>{shortAddress(proposal.destination)} · {proposal.network}</p>
              <small>Signature externe requise · {shortDateTime(proposal.created_at)}</small>
            </article>
          ))}
        </section>
      </aside>
    </div>
  )
}
