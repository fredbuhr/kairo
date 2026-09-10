import { createContext, useContext, type ReactNode } from 'react'
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
  slots: CockpitSlots
}

const CockpitContentContext = createContext<CockpitSlots | null>(null)
const dockPanelStyle = { height: '100%', overflow: 'auto' } as const

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

export default function CockpitShell({ slots }: CockpitShellProps) {
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
          onReady={createDefaultLayout}
        />
      </section>
    </CockpitContentContext.Provider>
  )
}
