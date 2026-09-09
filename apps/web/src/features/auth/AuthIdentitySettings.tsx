import { useSyncExternalStore } from 'react'

import {
  AUTH_CONFIGURATION,
  getAuthSnapshot,
  logoutKairo,
  subscribeAuthSession,
} from '../../lib/authSession'

export function AuthIdentitySettings() {
  const auth = useSyncExternalStore(subscribeAuthSession, getAuthSnapshot, getAuthSnapshot)

  return (
    <section className="auth-identity-settings">
      <header>
        <div><span className="kairo-kicker">IDENTITÉ</span><strong>{auth.username || auth.subject || 'Session KAIRO'}</strong></div>
        <b>{auth.enabled ? auth.authenticated ? 'AUTHENTIFIÉ' : 'HORS LIGNE' : 'MODE DEV'}</b>
      </header>
      <dl>
        <div><dt>Realm</dt><dd>{AUTH_CONFIGURATION.realm}</dd></div>
        <div><dt>Client</dt><dd>{AUTH_CONFIGURATION.clientId}</dd></div>
        <div><dt>Rôles</dt><dd>{auth.roles.length > 0 ? auth.roles.join(', ') : '—'}</dd></div>
        {auth.email && <div><dt>E-mail</dt><dd>{auth.email}</dd></div>}
      </dl>
      {auth.enabled && (
        <button type="button" onClick={() => void logoutKairo()}>Se déconnecter</button>
      )}
    </section>
  )
}
