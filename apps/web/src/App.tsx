const spaces = [
  'Command Center',
  'Today',
  'Projects',
  'Knowledge',
  'Mind 2D / 3D',
  'Gantt',
  'Calendar',
  'People',
  'Research',
  'Automations',
  'Agents',
  'Developer',
  'Crypto',
  'Finance',
  'Home',
  'Analytics',
  'Maps',
  'Approvals',
  'Activity',
  'System',
]

export default function App() {
  return (
    <main className="shell">
      <header>
        <div>
          <span className="eyebrow">PERSONAL AI OPERATING SYSTEM</span>
          <h1>KAIRO</h1>
        </div>
        <span className="status">foundation / architecture reset</span>
      </header>

      <section className="hero">
        <h2>One interface. One world model. Replaceable engines.</h2>
        <p>
          The permanent platform boundaries are now explicit: canonical state, durable workflows,
          policy, events, memory projections, realtime collaboration and specialist adapters.
        </p>
      </section>

      <section className="grid" aria-label="KAIRO spaces">
        {spaces.map((space) => (
          <article key={space} className="card">
            <span>{space}</span>
            <small>planned workspace</small>
          </article>
        ))}
      </section>
    </main>
  )
}
