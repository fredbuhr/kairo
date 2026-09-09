import Keycloak from 'keycloak-js'

export type KairoAuthSnapshot = {
  enabled: boolean
  initialized: boolean
  authenticated: boolean
  subject?: string | null
  username?: string | null
  email?: string | null
  roles: string[]
}

const AUTH_ENABLED = String(import.meta.env.VITE_KAIRO_AUTH_ENABLED ?? 'true').toLowerCase() !== 'false'
const KEYCLOAK_URL = String(import.meta.env.VITE_KEYCLOAK_URL || 'http://localhost:8081').replace(/\/$/, '')
const KEYCLOAK_REALM = String(import.meta.env.VITE_KEYCLOAK_REALM || 'kairo')
const KEYCLOAK_CLIENT_ID = String(import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'kairo-web')

let client: Keycloak | null = null
let initialization: Promise<void> | null = null
let initialized = false
const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

function redirectUri() {
  // Remove transient OIDC fragments/query parameters before asking Keycloak to come back to the app.
  return window.location.href.split(/[?#]/)[0]
}

function getClient() {
  if (!client) {
    client = new Keycloak({
      url: KEYCLOAK_URL,
      realm: KEYCLOAK_REALM,
      clientId: KEYCLOAK_CLIENT_ID,
    })
    client.onAuthSuccess = emit
    client.onAuthRefreshSuccess = emit
    client.onAuthLogout = emit
    client.onAuthError = emit
    client.onAuthRefreshError = emit
    client.onTokenExpired = () => {
      void refreshAccessToken().catch(() => undefined)
    }
  }
  return client
}

export async function initializeAuth(): Promise<void> {
  if (!AUTH_ENABLED) {
    initialized = true
    emit()
    return
  }
  if (initialization) return initialization

  initialization = (async () => {
    const keycloak = getClient()
    const authenticated = await keycloak.init({
      onLoad: 'login-required',
      pkceMethod: 'S256',
      checkLoginIframe: false,
      redirectUri: redirectUri(),
    })
    initialized = true
    emit()
    if (!authenticated) {
      await keycloak.login({ redirectUri: redirectUri() })
    }
  })().catch((error) => {
    initialization = null
    initialized = false
    emit()
    throw error
  })

  return initialization
}

export function getAuthSnapshot(): KairoAuthSnapshot {
  if (!AUTH_ENABLED) {
    return {
      enabled: false,
      initialized,
      authenticated: true,
      subject: 'development-user',
      username: 'development-user',
      email: null,
      roles: ['kairo-user'],
    }
  }

  const keycloak = client
  const parsed = keycloak?.tokenParsed as Record<string, unknown> | undefined
  const realmAccess = keycloak?.realmAccess
  return {
    enabled: true,
    initialized,
    authenticated: Boolean(keycloak?.authenticated && keycloak.token),
    subject: keycloak?.subject || null,
    username: typeof parsed?.preferred_username === 'string' ? parsed.preferred_username : null,
    email: typeof parsed?.email === 'string' ? parsed.email : null,
    roles: Array.isArray(realmAccess?.roles) ? [...realmAccess.roles] : [],
  }
}

export function subscribeAuthSession(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

async function refreshAccessToken(): Promise<string> {
  await initializeAuth()
  const keycloak = getClient()
  if (!keycloak.authenticated || !keycloak.token) {
    await keycloak.login({ redirectUri: redirectUri() })
    throw new Error('KAIRO authentication is required.')
  }
  try {
    await keycloak.updateToken(30)
  } catch (error) {
    keycloak.clearToken()
    emit()
    await keycloak.login({ redirectUri: redirectUri() })
    throw error
  }
  if (!keycloak.token) throw new Error('KAIRO authentication token is unavailable.')
  emit()
  return keycloak.token
}

export async function getAccessToken(): Promise<string | null> {
  if (!AUTH_ENABLED) return null
  return refreshAccessToken()
}

export async function authenticatedFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const token = await getAccessToken()
  const headers = new Headers(init.headers || {})
  if (token) headers.set('Authorization', `Bearer ${token}`)
  return fetch(input, { ...init, headers })
}

export async function logoutKairo() {
  if (!AUTH_ENABLED) return
  await initializeAuth()
  await getClient().logout({ redirectUri: redirectUri() })
}

export const AUTH_CONFIGURATION = {
  enabled: AUTH_ENABLED,
  keycloakUrl: KEYCLOAK_URL,
  realm: KEYCLOAK_REALM,
  clientId: KEYCLOAK_CLIENT_ID,
} as const
