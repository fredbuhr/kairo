type Props = {
  loading: boolean
  error: string | null
  selectedProjectId: string | null
}

export default function KnowledgeWorkspaceStateView({
  loading,
  error,
  selectedProjectId,
}: Props) {
  return (
    <>
      {error && <div className="error-panel">{error}</div>}

      {loading && !error && (
        <div className="progress-panel">
          <strong>Chargement de votre base documentaire KAIRO.</strong>
          <span>Les Documents sont fournis par le Core selon le propriétaire authentifié.</span>
        </div>
      )}

      {!loading && !error && !selectedProjectId && (
        <div className="progress-panel">
          <strong>Aucun projet sélectionné.</strong>
          <span>Sélectionnez un projet dans Projects ou Research pour afficher ses Documents.</span>
        </div>
      )}
    </>
  )
}
