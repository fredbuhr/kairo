import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  type ReactNode,
} from 'react'
import {
  DockviewReact,
  type DockviewReadyEvent,
  type IDockviewPanelProps,
} from 'dockview-react'
import 'dockview-react/dist/styles/dockview.css'

export type CockpitSlots = {
  command: ReactNode
  news: ReactNode
  research: ReactNode
}

type CockpitShellProps = {
  apiUrl?: string
  slots: CockpitSlots
  workspaceKey?: string
}

type WorkspaceLayoutEnvelope = {
  schema_version: number
  layout: unknown
}

const CockpitContentContext = createContext<CockpitSlots | null>(null)
const dockPanelStyle = { height: '100%', overflow: 'auto' } as const
const LAYOUT_SCHEMA_VERSION = 1
const DEFAULT_WORKSPACE_KEY = 'cockpit.main'
const DEFAULT_API_URL = (import.meta.env.VITE_KAIRO_API_URL || 'http://localhost:8000').replace(/\/$/, '')
const SAVE_DEBOUNCE_MS = 700

function useCockpitContent() {
  const value = useContext(CockpitContentContext)
  if (!value) throw new Error('Cockpit panels must render inside CockpitShell')
  return value
}

function CommandPanel(_props: IDockviewPanelProps) {
  return <div style={dockPanelStyle}>{useCockpitContent().command}</div>
}

function NewsPanel(_props: IDockviewPanelProps) {
  return <div style={dockPanelStyle}>{useCockpitContent().news}</div>
}

function ResearchPanel(_props: IDockviewPanelProps) {
  return <div style={dockPanelStyle}>{useCockpitContent().research}</div>
}

const components = {
  command: CommandPanel,
  news: NewsPanel,
  research: ResearchPanel,
}

function createDefaultLayout(event: DockviewReadyEvent) {
  event.api.addPanel({
    id: 'command-center',
    component: 'command',
    title: 'Command Center',
    minimumWidth: 320,
    minimumHeight: 260,
  })
  event.api.addPanel({
    id: 'news-intelligence',
    component: 'news',
    title: 'News Intelligence',
    position: { referencePanel: 'command-center', direction: 'right' },
    minimumWidth: 360,
    minimumHeight: 260,
  })
  event.api.addPanel({
    id: 'research',
    component: 'research',
    title: 'Research',
    position: { referencePanel: 'news-intelligence', direction: 'below' },
    minimumWidth: 360,
    minimumHeight: 300,
  })
}

async function loadWorkspaceLayout(apiUrl: string, workspaceKey: string) {
  const response = await fetch(
    `${apiUrl}/v1/ui/workspaces/${encodeURIComponent(workspaceKey)}/layout`,
  )
  if (response.status === 404) return null
  if (!response.ok) throw new Error(`KAIRO Core layout read failed (${response.status})`)
  const value = (await response.json()) as WorkspaceLayoutEnvelope
  if (
    value.schema_version !== LAYOUT_SCHEMA_VERSION ||
    typeof value.layout !== 'object' ||
    value.layout === null ||
    Array.isArray(value.layout)
  ) {
    return null
  }
  return value.layout
}

async function saveWorkspaceLayout(apiUrl: string, workspaceKey: string, layout: unknown) {
  const response = await fetch(
    `${apiUrl}/v1/ui/workspaces/${encodeURIComponent(workspaceKey)}/layout`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ schema_version: LAYOUT_SCHEMA_VERSION, layout }),
    },
  )
  if (!response.ok) throw new Error(`KAIRO Core layout save failed (${response.status})`)
}

export default function CockpitShell({
  apiUrl = DEFAULT_API_URL,
  slots,
  workspaceKey = DEFAULT_WORKSPACE_KEY,
}: CockpitShellProps) {
  const disposedRef = useRef(false)
  const cleanupRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    disposedRef.current = false
    return () => {
      disposedRef.current = true
      cleanupRef.current?.()
      cleanupRef.current = null
    }
  }, [])

  const onReady = useCallback(
    (event: DockviewReadyEvent) => {
      let saveTimer: number | undefined

      const initialize = async () => {
        let restored = false
        try {
          const saved = await loadWorkspaceLayout(apiUrl, workspaceKey)
          if (disposedRef.current) return
          if (saved) {
            event.api.fromJSON(saved as unknown as ReturnType<typeof event.api.toJSON>)
            restored = true
          }
        } catch (layoutError) {
          console.warn('KAIRO Cockpit layout restore failed; using default layout', layoutError)
        }

        if (disposedRef.current) return
        if (!restored) createDefaultLayout(event)

        const disposable = event.api.onDidLayoutChange(() => {
          if (saveTimer) window.clearTimeout(saveTimer)
          saveTimer = window.setTimeout(() => {
            void saveWorkspaceLayout(apiUrl, workspaceKey, event.api.toJSON()).catch(
              (layoutError) => {
                console.warn('KAIRO Cockpit layout save failed', layoutError)
              },
            )
          }, SAVE_DEBOUNCE_MS)
        })

        cleanupRef.current = () => {
          disposable.dispose()
          if (saveTimer) window.clearTimeout(saveTimer)
        }
      }

      void initialize()
    },
    [apiUrl, workspaceKey],
  )

  return (
    <CockpitContentContext.Provider value={slots}>
      <section
        className="cockpit-shell"
        aria-label="KAIRO Cockpit"
        style={{ height: 'min(78vh, 920px)', minHeight: 620 }}
      >
        <DockviewReact
          className="dockview-theme-abyss"
          style={{ width: '100%', height: '100%' }}
          components={components}
          onReady={onReady}
        />
      </section>
    </CockpitContentContext.Provider>
  )
}
