import React from 'react'
import ReactDOM from 'react-dom/client'

import App from './App'
import { initializeAuth } from './lib/authSession'
import { ProjectSelectionProvider } from './lib/projectSelection'
import './styles.css'

const root = ReactDOM.createRoot(document.getElementById('root')!)

function renderApp() {
  root.render(
    <React.StrictMode>
      <ProjectSelectionProvider>
        <App />
      </ProjectSelectionProvider>
    </React.StrictMode>,
  )
}

function renderAuthFailure(error: unknown) {
  const message = error instanceof Error ? error.message : 'Impossible d’établir la session KAIRO.'
  root.render(
    <React.StrictMode>
      <main className="shell">
        <section className="hero" aria-live="assertive">
          <span className="eyebrow">KAIRO · IDENTITÉ</span>
          <h1>Connexion sécurisée indisponible</h1>
          <p>{message}</p>
          <button type="button" onClick={() => window.location.reload()}>
            Réessayer
          </button>
        </section>
      </main>
    </React.StrictMode>,
  )
}

async function bootstrap() {
  try {
    await initializeAuth()
    renderApp()
  } catch (error) {
    renderAuthFailure(error)
  }
}

void bootstrap()
