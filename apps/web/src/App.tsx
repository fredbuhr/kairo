import KairoApp from './app/KairoApp'
import { LiveGraphBridge } from './features/graph/LiveGraphBridge'

export default function App() {
  return (
    <>
      <LiveGraphBridge />
      <KairoApp />
    </>
  )
}
