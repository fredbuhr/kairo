import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import App from './App'
import { LiveGraphBridge } from './features/graph/LiveGraphBridge'
import './styles.css'
import './brand.css'
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

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: true,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <LiveGraphBridge />
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
)
