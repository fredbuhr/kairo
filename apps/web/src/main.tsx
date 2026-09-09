import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import App from './App'
import { LiveGraphBridge } from './features/graph/LiveGraphBridge'
import { AUTH_CONFIGURATION, initializeAuth } from './lib/authSession'
import './styles.css'
import './brand.css'
import './auth.css'
import './graph-controls.css'
import './graph-filters.css'
import './context-today.css'
import './core-workspaces.css'
import './knowledge-workspace.css'
import './task-planning.css'
import './gantt-workspace.css'
import './calendar-workspace.css'
import './agents-workspace.css'
import './automations-workspace.css'
import './finance-workspace.css'
import './tools-workspace.css'
import './brain-mind-map.css'
import './desktop-runtime.css'
import './account-lifecycle.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: true,
    },
  },
})

const root = ReactDOM.createRoot(document.getElementById('root')!)

function renderCockpit() {
  root.render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <LiveGraphBridge />
        <App />
      </QueryClientProvider>
    </React.StrictMode>,
  )
}

function renderAuthFailure(error: unknown) {
  const message = error instanceof Error ? error.message : 'Impossible d’établir la session KAIRO.'
  root.render(
    <main className="auth-startup-error">
      <div className="auth-startup-mark" aria-hidden="true">K</div>
      <span>KAIRO · IDENTITÉ</span>
      <h1>Connexion sécurisée indisponible</h1>
      <p>{message}</p>
      <small>{AUTH_CONFIGURATION.keycloakUrl} · realm {AUTH_CONFIGURATION.realm}</small>
      <button type="button" onClick={() => window.location.reload()}>Réessayer</button>
    </main>,
  )
}

async function bootstrap() {
  try {
    await initializeAuth()
    renderCockpit()
  } catch (error) {
    renderAuthFailure(error)
  }
}

void bootstrap()
